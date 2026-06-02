import numpy as np
import cv2
import time
import argparse


from inference_tf_lite import init_interpreter, inference_frame, postprocessing

def draw_match(img1, img2, pts1, pts2):
    
    def draw_corners(img, corners):
        for i in range(len(corners)):
            start = tuple(corners[i-1][0].astype(int))
            end = tuple(corners[i][0].astype(int))
            cv2.line(img, start, end, (0, 255, 0), 4)
        return img
    
    def put_text(img, num_matches):
        return cv2.putText(img, f'Matches: {num_matches}', (25, 25), cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 100), 2)
    
    h, w = img1.shape[:2]
    corners_img1 = np.array([[40, 40], [w-41, 40], [w-41, h-41], [40, h-41]], dtype=np.float32).reshape(-1, 1, 2)
    img1 = draw_corners(img1, corners_img1)
    if len(pts1) <= 10 or len(pts2) <= 10:
        return put_text(np.concatenate([img1, img2], axis=1), 0)
    
    H, mask = cv2.findHomography(pts1, pts2, cv2.USAC_MAGSAC, 2, maxIters=10000, confidence=0.999)
    mask = mask.flatten()
    if mask.sum() <= 10:
        return put_text(np.concatenate([img1, img2], axis=1), 0)
    
    corners_img2 = cv2.perspectiveTransform(corners_img1, H)
    img2 = draw_corners(img2, corners_img2)

    img2 = img2.copy()
    img2 = draw_corners(img2, corners_img2)

    pts1 = [cv2.KeyPoint(p[0], p[1], 5) for p in pts1]
    pts2 = [cv2.KeyPoint(p[0], p[1], 5) for p in pts2]
    matches = [cv2.DMatch(i,i,0) for i in range(len(mask)) if mask[i]]
    
    img_matches = cv2.drawMatches(img1, pts1, img2, pts2, matches, None,
                                  matchColor=(127, 127, 0), flags=2)
    img_matches = put_text(img_matches, len(matches))

    return img_matches


def match(desc1, desc2, threshold=0.5):
    if desc1.shape[0] == 0 or desc2.shape[0] == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)

    cossim = np.dot(desc1, desc2.T) 

    match12 = np.argmax(cossim, axis=1) 
    match21 = np.argmax(cossim, axis=0)  

    idx1 = np.arange(len(match12))
    mutual = match21[match12] == idx1

    idx1 = idx1[mutual]
    idx2 = match12[mutual]
    scores = cossim[idx1, idx2]
    
    if threshold > -1:
        mask = scores > threshold
        idx1 = idx1[mask]
        idx2 = idx2[mask]
        scores = scores[mask]
        
    return idx1, idx2


if __name__ == '__main__':
    model_path = "models/EdgePoint2/edgepoint2_E64_640_480.tflite"

    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=str, help='camera or video file')
    parser.add_argument('--camid', type=int, default=0)
    parser.add_argument('--top_k', type=int, default=4096)
    parser.add_argument('--match_threshold', type=float, default=0.5)
    parser.add_argument('--model', type=str, default=model_path)
    parser.add_argument('--no_vis', action='store_true')
    
    args = parser.parse_args()
    
    interpreter, input_details, output_details = init_interpreter(args.model)
    input_shape = input_details[0]['shape']
    
    if args.input == 'camera':
        cap = cv2.VideoCapture(args.camid)
    else:
        cap = cv2.VideoCapture(args.input)
    
    frozen_im = None
    frozen_kpts = None
    frozen_desc = None

    sum_fps = 0
    frame_num = 0
    # open('output.txt', 'w').close()
    # np.set_printoptions(threshold=np.inf)
    # file = open('output.txt', 'a')
    while 1:
        frame_num += 1
        start_time = time.perf_counter()

        ret, im = cap.read()
        if not ret:
            break
        
        _, H, W, _ = input_shape
        #print(input_shape)
       
        vis_im = cv2.resize(im, (640, 480))

        model_input = cv2.resize(im, (W//32*32, H//32*32))
        model_input = cv2.cvtColor(model_input, cv2.COLOR_BGR2RGB)
        model_input = model_input.astype(np.float32)

        data, input_shape = inference_frame(
            model_input,
            interpreter,
            input_details,
            output_details
        )

        output = postprocessing(data, input_shape, top_k=args.top_k)



        # file.write(f"{output}\n\nEOF\n\n")
        # print("output of frame is written")




        kpts = output[0]['keypoints']
        desc = output[0]['descriptors']
        
        if frozen_im is None:
            frozen_im = vis_im
            frozen_kpts = kpts
            frozen_desc = desc
            continue
        
        idxs1, idxs2 = match(frozen_desc, desc, args.match_threshold)

        if args.no_vis:
            pass
        else:
            matched_im = draw_match(frozen_im, vis_im.copy(), frozen_kpts[idxs1], kpts[idxs2])
            cv2.imshow('matches', matched_im)
            key = cv2.waitKey(1)
            if key == ord('q'):
                break
            elif key == ord(' '):
                frozen_im = im
                frozen_kpts = kpts
                frozen_desc = desc

        end_time = time.perf_counter()
        frame_time = end_time - start_time
        fps = 1 / frame_time
        sum_fps += fps
        #print(f'FPS: {fps:.1f}')

    #file.close()
    print(f'AVG FPS: {(sum_fps / frame_num):1f}')
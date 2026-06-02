import numpy as np
import tflite_runtime.interpreter as tflite
import cv2
import os
import torch
import torch.nn.functional as F
import time
import argparse


def init_interpreter(model_path):
    os.environ["ARMNN_LOG_LEVEL"] = "debug"
    DELEGATE_PATH = "docker_output/aarch64_build/delegate/libarmnnDelegate.so"

    delegate = tflite.load_delegate(
        DELEGATE_PATH,
        options={
            "backends": "GpuAcc,CpuAcc"
        }
    )

    interpreter = tflite.Interpreter(
        model_path=model_path,
        experimental_delegates=[delegate]
    )

    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    return interpreter, input_details, output_details


def inference_frame(frame_in_cv2, interpreter, input_details, output_details):
    data = []
    img = frame_in_cv2.astype(np.float32) / 255

    input_shape = input_details[0]['shape']
    input_dtype = input_details[0]['dtype']

    input_data = np.expand_dims(img, axis=0)

    interpreter.set_tensor(input_details[0]['index'], input_data.astype(input_dtype))
    interpreter.invoke()

    for i, out in enumerate(output_details):
        data.append(interpreter.get_tensor(out['index']))
    
    return data, input_shape

def postprocessing(data, input_shape, score_thresh=-5, top_k=4096):

    def sample(dense, kpts, *, norm=True, align_corners=False):
        if dense.shape[-1] < 256:
            dense = dense.permute(0, 3, 1, 2)

        desc = F.grid_sample(
            dense,
            kpts,
            mode='bilinear',
            align_corners=align_corners
        )

        if norm:
            desc = F.normalize(desc, p=2, dim=1)

        return desc

    raw_desc, raw_detect = data
    raw_desc = torch.tensor(raw_desc, dtype=torch.float32)


    heatmap = np.squeeze(raw_detect, axis=(0, 3))
    B, oH, oW, _ = raw_detect.shape
    nH = oH // 32 * 32
    nW = oW // 32 * 32
    size = torch.tensor([nW, nH], dtype=torch.float32)
    scale = np.array([oW/nW, oH/nH], dtype=np.float32)

    pooled = cv2.dilate(heatmap, np.ones((5, 5)))

    detect1 = (heatmap == pooled)

    detect1[:, :4] = False  
    detect1[:, -4:] = False 
    detect1[:4, :] = False   
    detect1[-4:, :] = False 

    detect2 = heatmap > score_thresh

    detect = np.logical_and(detect1, detect2)

    ys, xs = np.where(detect)

    kpts = np.stack([xs, ys], axis=1)

    scores = heatmap[ys, xs]

    if len(scores) > top_k:
        idx = np.argsort(scores)[-top_k:]
        kpts = kpts[idx]
        scores = scores[idx]

    kpts_torch = torch.tensor(
        (kpts + 0.5).reshape(1, -1, 1, 2) / size.numpy() * 2 - 1,
        dtype=torch.float32
    )

    desc = sample(raw_desc, kpts_torch)[0, :, :, 0].mT.contiguous()
    _, orig_h, orig_w, _ = input_shape
    h, w = heatmap.shape
    desc = np.array(desc, dtype=np.float32)


    return [
        {'keypoints': kpts * scale,
         'scores': scores,
         'descriptors': desc}]


if __name__ == '__main__':
    model_path = "tflite_models/U128_640x480.tflite"
    input_path = "demo_video/demo_video.mp4"

    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, default=input_path)
    parser.add_argument('--model', type=str, default=model_path)
    
    args = parser.parse_args()

    
    interpreter, input_details, output_details = init_interpreter(args.model)
    input_shape = input_details[0]['shape']
    
    frozen_im = None
    frozen_kpts = None
    frozen_desc = None

    cap = cv2.VideoCapture(input_path)

    sum_fps = 0
    frame_num = 0
    # open('output.txt', 'w').close()
    # np.set_printoptions(threshold=np.inf)
    # file = open('output.txt', 'a')
    print("The model is working")
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

        #print(f"OUTPUT:\n{data}")

        #output = postprocessing(data, input_shape, top_k=args.top_k)



        # file.write(f"{output}\n\nEOF\n\n")
        # print("output of frame is written")




        # kpts = output[0]['keypoints']
        # desc = output[0]['descriptors']
        
        # if frozen_im is None:
        #     frozen_im = vis_im
        #     frozen_kpts = kpts
        #     frozen_desc = desc
        #     continue
        
        # idxs1, idxs2 = match(frozen_desc, desc, args.match_threshold)

        # if args.no_vis:
        #     pass
        # else:
        #     matched_im = draw_match(frozen_im, vis_im.copy(), frozen_kpts[idxs1], kpts[idxs2])
        #     cv2.imshow('matches', matched_im)
        #     key = cv2.waitKey(1)
        #     if key == ord('q'):
        #         break
        #     elif key == ord(' '):
        #         frozen_im = im
        #         frozen_kpts = kpts
        #         frozen_desc = desc

        end_time = time.perf_counter()
        frame_time = end_time - start_time
        fps = 1 / frame_time
        sum_fps += fps
        #print(f'FPS: {fps:.1f}')

    #file.close()
    print(f'AVG FPS: {(sum_fps / frame_num):1f}')
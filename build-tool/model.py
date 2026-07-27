import torch
import torch.nn as nn
import torch.nn.functional as F

from .modules import BasicLayer, ResNetLayer


class EdgePoint2(nn.Module):

    def __init__(self, c1, c2, c3, c4, cdesc, cdetect):
        super().__init__()
        self.norm = nn.InstanceNorm2d(1)
        #self.norm = nn.BatchNorm2d(1)

        csum = c2 + c3 + c4
        C = 3

        self.block1 = nn.Sequential(
            BasicLayer(1, c1, 4, 2, 1),
            BasicLayer(c1, c2),
            ResNetLayer(c2, c2)
        )
        self.block2 = ResNetLayer(c2, c3)
        self.block3 = ResNetLayer(c3, c4)
        
        # self.desc1 = nn.Identity()
        # self.desc2 = nn.Identity()
        # self.desc3 = nn.Identity()
        self.desc_head = nn.Sequential(
            nn.Conv2d(csum, csum, 1),
            BasicLayer(csum, csum, groups=csum//16),
            nn.Conv2d(csum, cdesc, 1)
        )
        
        self.conv1 = nn.Conv2d(c2, cdetect, 1)
        self.conv2 = nn.Conv2d(c3, cdetect, 1)
        self.conv3 = nn.Conv2d(c4, cdetect, 1)

        self.channel_mean = nn.Conv2d(
            in_channels=C,
            out_channels=1,
            kernel_size=1,
            bias=False
        )
        
        self.score_head = nn.Sequential(
            nn.Conv2d(cdetect, cdetect, 3, 1 ,1),
            nn.ReLU(True),
            nn.Conv2d(cdetect, cdetect, 3, 1, 1),
            nn.ReLU(True),
            nn.Conv2d(cdetect, 4, 3, 1, 1),
            nn.PixelShuffle(2)
        )

        self.pool1 = nn.Conv2d(c2, c2, kernel_size=2, stride=2, groups=c2, bias=False)
        self.pool2 = nn.Conv2d(c2, c2, kernel_size=2, stride=2, groups=c2, bias=False)
        self.pool3 = nn.Conv2d(c3, c3, kernel_size=4, stride=4, groups=c3, bias=False)


        with torch.no_grad():
            self.pool1.weight.fill_(1.0 / 4)
            self.pool2.weight.fill_(1.0 / 4 + 0.000001)
            self.pool3.weight.fill_(1.0 / 16)
            self.channel_mean.weight.fill_(1.0 / C)


    def forward(self, x):
        #with torch.no_grad():
        #if x.shape[1] > 1:

        #x = x.mean(dim=1, keepdim = True)
        x = self.channel_mean(x)

        # x = x * 0.00784313725 - 1.0
        # x = x * 2.0 - 1.0
        x = self.norm(x)

        print("\n\nSHAPES:")
        x1 = self.block1(x)
        print(x1.shape)
        _x2 = self.pool1(x1)#F.avg_pool2d(x1, 2, 2)
        print("AVG: ", _x2.shape)
        x2 = self.pool2(_x2)#F.avg_pool2d(_x2, 2, 2)
        print("AVG: ", x2.shape)
        x2 = self.block2(x2)
        print(x2.shape)
        x3 = self.pool3(x2)#F.avg_pool2d(x2, 4, 4)
        print("AVG: ", x3.shape)
        x3 = self.block3(x3)
        print(x3.shape)
        print("\n\n")

        desc = torch.cat([
            _x2,
            #self.desc1(_x2),
            F.interpolate(x2, scale_factor=2, mode='bilinear', align_corners=False),
            F.interpolate(x3, scale_factor=8, mode='bilinear', align_corners=False),
        ], 1)
        desc = self.desc_head(desc)
        
        score = self.conv1(x1) \
            +F.interpolate(self.conv2(x2), scale_factor=4, mode='bilinear', align_corners=False) \
            +F.interpolate(self.conv3(x3), scale_factor=16, mode='bilinear', align_corners=False)
        score = self.score_head(score)
        
        return desc, score

    
    def sample(self, dense, kpts, *, norm=True, align_corners=False):
        desc = F.grid_sample(dense, kpts, mode='bilinear', align_corners=align_corners)
        return F.normalize(desc, 2, 1) if norm else desc
    

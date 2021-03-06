import os
import sys

import numpy as np
import pdb
from PIL import Image
from torch.utils import data

from .config_SYN import root, raw_img_path, raw_mask_path
from ..encoder import DataEncoder
from ..shuffleData import getShuffleIdx
from config import cfg
from utils.timer import Timer

import torch



def default_loader(path):
    return Image.open(path)




class SYN(data.Dataset):
    def __init__(self, mode, list_filename, simul_transform=None, transform=None, target_transform=None):
        
        self.img_root = raw_img_path
        self.mask_root = raw_mask_path
        list_file = root + '/' + list_filename

        self.simul_transform = simul_transform
        self.transform = transform
        self.target_transform = target_transform

        self.data_encoder = DataEncoder()

        self.fnames = []
        self.boxes = []
        self.labels = []
        # self.ori_boxes = []
        # self.ori_labels = []


        
        with open(list_file) as f:
            lines = f.readlines()
            self.num_samples = len(lines)

        for line in lines:
            splited = line.strip().split()
            self.fnames.append(splited[0])

            num_objs = int(splited[1])
            box = []
            label = []
            for i in range(num_objs):
                xmin = splited[2+5*i]
                ymin = splited[3+5*i]
                xmax = splited[4+5*i]
                ymax = splited[5+5*i]
                c = splited[6+5*i]
                box.append([float(xmin),float(ymin),float(xmax),float(ymax)])
                label.append(int(c))
            self.boxes.append(torch.Tensor(box))
            # self.ori_boxes.append(torch.Tensor(box))
            self.labels.append(torch.LongTensor(label))
        self.img_loader = default_loader

    def __getitem__(self, idx):

        fname = self.fnames[idx]
        # _t = {'trans':Timer(), 'load' : Timer(), 'compute':Timer()}
        # _t['load'].tic()
        img = self.img_loader(os.path.join(self.img_root,fname))
        mask = self.img_loader(os.path.join(self.mask_root,fname))
        
        # _t['load'].toc(average=False)
        boxes = self.boxes[idx].clone()
        labels = self.labels[idx]
        ori_labels = self.labels[idx].clone()
        
        # _t['trans'].tic()
        # flip and rescale
        if self.simul_transform is not None:
            img, mask, boxes = self.simul_transform(img, mask, boxes)
        # _t['trans'].toc(average=False)

        # _t['compute'].tic()
        ori_boxes = boxes.clone()
        # Scale bbox locaitons to [0,1]
        w,h = img.size
        boxes = boxes/torch.Tensor([w,h,w,h]).expand_as(boxes)
        

        # Encode bbx & objects labels.
        boxes, labels = self.data_encoder.encode(boxes, labels)

        # _t['compute'].toc(average=False)
        # print '{:.3f}s {:.3f}s {:.3f}s'.format(_t['trans'].average_time,_t['load'].average_time,_t['compute'].average_time)
        # gen roi data for roipooling 
        shuffle_idx = getShuffleIdx(ori_boxes.size()[0])

        shuffle_idx = torch.from_numpy(shuffle_idx.astype(np.int64))
        ori_boxes = torch.index_select(ori_boxes, 0, shuffle_idx)

        ori_labels = torch.index_select(ori_labels, 0, shuffle_idx)
        # Normalize
        if self.transform is not None:
            img = self.transform(img)
        # change the seg labels 255->19    
        if self.target_transform is not None:
            mask = self.target_transform(mask)
        # pdb.set_trace()
        
        return img, mask, boxes, labels, ori_boxes, ori_labels

    def __len__(self):
        return self.num_samples

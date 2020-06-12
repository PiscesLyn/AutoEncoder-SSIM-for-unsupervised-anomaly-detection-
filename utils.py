import numpy as np
import math
import cv2
import random
import os


def read_img(img_path, grayscale):
    if grayscale:
        im = cv2.imread(img_path, 0)
    else:
        im = cv2.imread(img_path)
    return im


def random_crop(image, new_size):
    h, w = image.shape[:2]
    y = np.random.randint(0, h - new_size[0])
    x = np.random.randint(0, w - new_size[1])
    image = image[y:y+new_size[0], x:x+new_size[1]]
    return image


def rotate_image(img, angle, crop):
    h, w = img.shape[:2]
    angle %= 360
    M_rotate = cv2.getRotationMatrix2D((w/2, h/2), angle, 1)
    img_rotated = cv2.warpAffine(img, M_rotate, (w, h))
    if crop:
        angle_crop = angle % 180
        if angle_crop > 90:
            angle_crop = 180 - angle_crop
        theta = angle_crop * np.pi / 180.0
        hw_ratio = float(h) / float(w)
        tan_theta = np.tan(theta)
        numerator = np.cos(theta) + np.sin(theta) * tan_theta
        r = hw_ratio if h > w else 1 / hw_ratio
        denominator = r * tan_theta + 1
        crop_mult = numerator / denominator
        w_crop = int(round(crop_mult*w))
        h_crop = int(round(crop_mult*h))
        x0 = int((w-w_crop)/2)
        y0 = int((h-h_crop)/2)
        img_rotated = img_rotated[y0:y0+h_crop, x0:x0+w_crop]
    return img_rotated


def random_rotate(img, angle_vari, p_crop):
    angle = np.random.uniform(-angle_vari, angle_vari)
    crop = False if np.random.random() > p_crop else True
    return rotate_image(img, angle, crop)


def generate_image_list(args):
    filenames = os.listdir(args.train_data_dir)
    num_imgs = len(filenames)
    num_ave_aug = int(math.floor(args.augment_num/num_imgs))
    rem = args.augment_num - num_ave_aug*num_imgs
    lucky_seq = [True]*rem + [False]*(num_imgs-rem)
    random.shuffle(lucky_seq)

    img_list = [
        (os.sep.join([args.train_data_dir, filename]), num_ave_aug+1 if lucky else num_ave_aug)
        for filename, lucky in zip(filenames, lucky_seq)
    ]

    return img_list


def augment_images(filelist, args):
    for filepath, n in filelist:
        img = read_img(filepath, args.grayscale)
        if img.shape[:2] != args.im_resize:
            img = cv2.resize(img, args.im_resize)
        filename = filepath.split(os.sep)[-1]
        dot_pos = filename.rfind('.')
        imgname = filename[:dot_pos]
        ext = filename[dot_pos:]

        print('Augmenting {} ...'.format(filename))
        for i in range(n):
            img_varied = img.copy()
            varied_imgname = '{}_{:0>3d}_'.format(imgname, i)
            
            if random.random() < args.p_rotate:
                img_varied_ = random_rotate(
                    img_varied,
                    args.rotate_angle_vari,
                    args.p_rotate_crop)
                if img_varied_.shape[0] >= args.patch_size[0] and img_varied_.shape[1] >= args.patch_size[1]:
                    img_varied = img_varied_
                varied_imgname += 'r'

            if random.random() < args.p_crop:
                img_varied = random_crop(
                    img_varied,
                    args.patch_size)
                varied_imgname += 'c'

            if random.random() < args.p_horizonal_flip:
                img_varied = cv2.flip(img_varied, 1)
                varied_imgname += 'h'

            if random.random() < args.p_vertical_flip:
                img_varied = cv2.flip(img_varied, 0)
                varied_imgname += 'v'

            output_filepath = os.sep.join([
                args.aug_dir,
                '{}{}'.format(varied_imgname, ext)])
            cv2.imwrite(output_filepath, img_varied)


def get_patch(image, new_h, new_w, stride):
    h, w = image.shape[:2]
    i, j = new_h, new_w
    patch = []
    while i <= h:
        while j <= w:
            patch.append(image[i - new_h:i, j - new_w:j])
            j += stride
        j = new_w
        i += stride
    return np.array(patch)


def patch2img(patches, im_size, patch_size, stride):
    img = np.zeros((im_size[0], im_size[1], patches.shape[3]+1))
    i, j = patch_size[0], patch_size[1]
    k = 0
    while i <= im_size[0]:
        while j <= im_size[1]:
            img[i - patch_size[0]:i, j - patch_size[1]:j, :-1] += patches[k]
            img[i - patch_size[0]:i, j - patch_size[1]:j, -1] += np.ones((patch_size[0], patch_size[1]))
            k += 1
            j += stride
        j = patch_size[1]
        i += stride
    mask=np.repeat(img[:,:,-1][...,np.newaxis], patches.shape[3], 2)
    img = img[:,:,:-1]/mask
    return img


def set_img_color(img, predict_mask, weight_foreground, grayscale):
    if grayscale:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    origin = img
    img[np.where(predict_mask == 255)] = (0,0,255)
    cv2.addWeighted(img, weight_foreground, origin, (1 - weight_foreground), 0, img)
    return img
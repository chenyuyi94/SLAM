import tensorflow as tf
import numpy as np
import bisect
import scipy.ndimage


def _find_label(groundtruth, timestamp):
    return bisect.bisect_left(groundtruth, timestamp)


def _absolute_position(groundtruth):
    x = groundtruth[0:3]
    q = groundtruth[3:7]

    # compute euler angles
    phi = np.arctan2(2*(q[0]*q[1] + q[2]*q[3]), 1-2*(np.square(q[1]) + np.square(q[2])))
    theta = np.arcsin(2*(q[0]*q[2] - q[3]*q[1]))
    psi = np.arctan2(2*(q[0]*q[3] + q[1]*q[2]), 1-2*(np.square(q[2]) + np.square(q[3])))

    # compute rotation matrix
    rot_mat = np.zeros((3, 3))
    rot_mat[0, 0] = np.cos(theta)*np.cos(phi)
    rot_mat[1, 0] = np.cos(theta)*np.sin(phi)
    rot_mat[2, 0] = -np.sin(theta)

    rot_mat[0, 1] = np.sin(psi)*np.sin(theta)*np.cos(phi) - np.cos(psi)*np.sin(phi)
    rot_mat[1, 1] = np.sin(psi)*np.sin(theta)*np.sin(phi) + np.cos(psi)*np.cos(phi)
    rot_mat[2, 1] = np.sin(psi)*np.cos(theta)

    rot_mat[0, 2] = np.cos(psi)*np.sin(theta)*np.cos(phi) + np.sin(psi)*np.sin(phi)
    rot_mat[1, 2] = np.cos(psi)*np.sin(theta)*np.sin(phi) - np.sin(psi)*np.cos(phi)
    rot_mat[2, 2] = np.cos(psi)*np.cos(theta)

    # compute angular velocities
    w_abs = np.arccos((np.trace(rot_mat)-1)/2)
    w = np.zeros(3)
    w[0] = 1/(2*np.sin(w_abs)) * (rot_mat[2, 1]-rot_mat[1, 2]) * w_abs
    w[1] = 1/(2*np.sin(w_abs)) * (rot_mat[0, 2]-rot_mat[2, 0]) * w_abs
    w[2] = 1/(2*np.sin(w_abs)) * (rot_mat[1, 0]-rot_mat[0, 1]) * w_abs

    return np.concatenate((x, w), 0)


def _image_preprocessing(image_rgb, image_depth):
    img_rgb = image_rgb.eval()
    img_depth = image_depth.eval()

    # scale depth image to values between 0 and 255
    img_depth -= img_depth.min()
    img_depth = (img_depth * 255.0/img_depth.max()) # maybe problem with float

    # images are concatenated to 4 channels
    img = np.concatenate((img_rgb, img_depth), axis=2)

    # scale down image
    return scipy.ndimage.zoom(img, (224.0/480, 224.0/640, 1))


def _initialise_dataset(dataset, reader, path):
    rgbd = np.loadtxt(path+dataset+"/associated_data.txt", dtype="str",  unpack=False)
    groundtruth = np.loadtxt(path+dataset+"/groundtruth.txt", dtype="str",  unpack=False)

    # determine the number of files in dataset
    num_examples = rgbd.shape[0]

    # read out the labels
    labels = groundtruth[:, 1:]

    # drop every nth element out of list
    # n = 3
    # rgbd = np.delete(rgbd, np.arange(0, rgbd.size, 3))

    # FIFO queue of filenames
    filename_queue_rgb = tf.train.string_input_producer(path+dataset + "/" + tf.convert_to_tensor(rgbd[:, 1]))
    filename_queue_depth = tf.train.string_input_producer(path+dataset + "/" + tf.convert_to_tensor(rgbd[:, 3]))

    key_rgb, value_rgb = reader.read(filename_queue_rgb)
    key_depth, value_depth = reader.read(filename_queue_depth)

    # Decoder for record read by the reader
    image_rgb = tf.image.decode_png(value_rgb)
    image_depth = tf.image.decode_png(value_depth)

    # compute absolute position
    abs_pos = np.zeros((num_examples, 6))
    for i in range(num_examples):
        abs_pos[i] = _absolute_position(labels[_find_label(groundtruth[:, 0], rgbd[i, 0])].astype(np.float))

    return image_rgb, image_depth, abs_pos, num_examples


# folder, where the datasets are stored
path = "/home/aw/PycharmProjects/"

# Datasets as a List of strings
datasets = ["rgbd_dataset_freiburg1_rpy", "rgbd_dataset_freiburg1_xyz"]

# Reader for the file format
reader = tf.WholeFileReader()

# Initialise datasets
image_rgb = []
image_depth = []
num_examples = []
abs_pos = []
for i in range(len(datasets)):
    rgb, depth, pos, num = _initialise_dataset(datasets[i], reader, path)
    image_rgb.append(rgb)
    image_depth.append(depth)
    abs_pos.append(pos)
    num_examples.append(num)
init_op = tf.initialize_all_variables()

with tf.Session() as sess:
    sess.run(init_op)
    coord = tf.train.Coordinator()
    threads = tf.train.start_queue_runners(coord=coord)

    for dataset_index in range(len(datasets)):

        for index in range(num_examples[dataset_index]):
            img = _image_preprocessing(image_rgb[dataset_index], image_depth[dataset_index])
            position = abs_pos[dataset_index][index]

            # compute relative position
            if index == 0:
                prior_pos = position
            else:
                rel_pos = prior_pos - position
                print (rel_pos)
            print(index)

    coord.request_stop()
    coord.join(threads)


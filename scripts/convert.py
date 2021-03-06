import argparse
import logging
import numpy as np

from models.yolov3 import YOLOv3

parser = argparse.ArgumentParser(description='Convert pre-trained weights')
parser.add_argument('input', type=str, help='Input weights file')
parser.add_argument('output', type=str, help='Output weights file')
parser.add_argument('classes', type=int, help='Num classes')
parser.add_argument('-d', dest='debug', action='store_true', help='debug mode')

YOLOV3_LAYER_LIST = [
        'darknet-53',
        'yolo_conv_0',
        'yolo_output_0',
        'yolo_conv_1',
        'yolo_output_1',
        'yolo_conv_2',
        'yolo_output_2',
        ]


def load_darknet_weights(model, weights_file):
    '''
    Sets the weights of a YOLOv3 model from a darknet weights file.
    '''
    wf = open(weights_file, 'rb')
    major, minor, revision, seen, _ = np.fromfile(wf, dtype=np.int32, count=5)

    for layer_name in YOLOV3_LAYER_LIST:
        sub_model = model.get_layer(layer_name)
        for i, layer in enumerate(sub_model.layers):
            if not layer.name.startswith('conv2d'):
                continue

            batch_norm = None
            if i + 1 < len(sub_model.layers) and \
                    sub_model.layers[i + 1].name.startswith('batch_norm'):
                batch_norm = sub_model.layers[i + 1]

            logging.info("{}/{} {}".format(
                sub_model.name, layer.name, 'bn' if batch_norm else 'bias'))

            filters = layer.filters
            size = layer.kernel_size[0]
            in_dim = layer.get_input_shape_at(0)[-1]

            if batch_norm is None:
                conv_bias = np.fromfile(wf, dtype=np.float32, count=filters)
            else:
                # darknet [beta, gamma, mean, variance].
                bn_weights = np.fromfile(wf, dtype=np.float32, count=4 * filters)
                # tf [gamma, beta, mean, variance].
                bn_weights = bn_weights.reshape((4, filters))[[1, 0, 2, 3]]

            # darknet shape (out_dim, in_dim, height, width).
            conv_shape = (filters, in_dim, size, size)
            conv_weights = np.fromfile(wf, dtype=np.float32, count=np.product(conv_shape))
            # tf shape [height, width, in_dim, out_dim].
            conv_weights = conv_weights.reshape(conv_shape).transpose([2, 3, 1, 0])

            if batch_norm is None:
                layer.set_weights([conv_weights, conv_bias])
            else:
                layer.set_weights([conv_weights])
                batch_norm.set_weights(bn_weights)

    assert len(wf.read()) == 0, 'failed to read all data'
    wf.close()


def main(args):
    yolo = YOLOv3(classes=args.classes)

    yolo.summary()
    logging.info('Model created!')

    load_darknet_weights(yolo, args.input)
    logging.info('Weights loaded!')

    img = np.random.random((1, 320, 320, 3)).astype(np.float32)
    output = yolo(img)
    logging.info('Inference check done!')

    yolo.save_weights(args.output)
    logging.info('Weights saved!')


if __name__ == "__main__":
    args = parser.parse_args()

    log_level = logging.INFO

    if args.debug:
        log_level = logging.DEBUG

    logging.basicConfig(level=log_level,
            format='%(levelname)s:%(asctime)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M')


    main(args)

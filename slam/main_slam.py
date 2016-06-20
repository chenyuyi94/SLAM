from slam.network.cnn_model import VGG16Model
from slam.network.lstm_model import LSTMmodel
import tensorflow as tf
from slam.utils.logging_utils import get_logger


# model parameters
lstm_layers = 3
lstm_cells_in_layer = 100
logger = get_logger()

def model():
    batch_size = 1
    img_h = 224
    img_w = 224
    vgg_model = VGG16Model([img_h, img_w, 4], batch_size, 1000)
    cnn_output, ground_truth = vgg_model.build_graph()
    lstm_model = LSTMmodel(cnn_output, layer_size=1000, layers=10, output_dim=6, ground_truth=ground_truth)
    lstm_model.build_graph()

    loss = lstm_model.add_loss()
    apply_gradient_op = lstm_model.add_optimizer()
    
    session = tf.Session()
    session.run(tf.initialize_all_variables())
    for step in xrange(300):
        logger.info('Executing step:{}'.format(step))
        session.run([apply_gradient_op, loss])


if __name__ == '__main__':
    model()
import tensorflow.keras as keras
import os
from itertools import chain

from keras.callbacks import EarlyStopping, ReduceLROnPlateau, Callback, ModelCheckpoint
from keras.optimizers import RMSprop, Adam

import pandas as pd
from keras.applications import Xception, ResNet50, InceptionV3, MobileNet, VGG19, DenseNet121, InceptionResNetV2, VGG16
from keras.layers import LSTM, ConvLSTM2D
import BuildModel_basic
import DatasetBuilder
import poseGatedNet
from numpy.random import seed, shuffle
from keras.models import load_model
from tensorflow import set_random_seed
from collections import defaultdict
import pickle

class TestCallback(Callback):
    def __init__(self, test_gen,test_steps):
        self.test_gen = test_gen
        self.test_loss = []
        self.test_acc = []
        self.test_steps = test_steps
    def on_epoch_end(self, epoch, logs={}):
        #x, p, y = self.test_data
        loss, acc = self.model.evaluate_generator(generator=self.test_gen, steps=self.test_steps, callbacks=None, use_multiprocessing=True, verbose=1)
        self.test_loss.append(loss)
        self.test_acc.append(acc)
        print('\nTesting loss: {}, Testing acc: {}\n'.format(loss, acc))


def train_eval_network(dataset_name, train_gen, validate_gen, test_gen, seq_len, epochs, batch_size,
                       batch_epoch_ratio, initial_weights, size, cnn_arch, learning_rate,
                       optimizer, cnn_train_type, pre_weights, lstm_conf, len_train, len_valid, len_test, dropout, classes,
                       patience_es=15, patience_lr=5):
    """the function build, compile fit and evaluate a certain architechtures on a dataset"""
    set_random_seed(2)
    seed(1)
    result = dict(dataset=dataset_name, cnn_train=cnn_train_type,
                  cnn=cnn_arch.__name__, lstm=lstm_conf[0].__name__, epochs=epochs,
                  learning_rate=learning_rate, batch_size=batch_size, dropout=dropout,
                  optimizer=optimizer[0].__name__, initial_weights=initial_weights, seq_len=seq_len)
    print("run experimnt " + str(result))
    bestModelPath = '/gdrive/My Drive/THESIS/Data/' + str(dataset_name) + '_poseGatedNetBestModel.h5'
    model = None
    if use_new_model:
        model = poseGatedNet.getModel(size=size, seq_len=seq_len , cnn_weight = 'imagenet',lstm_conf = lstm_conf )
    else:
        print('getting the model from ',bestModelPath)
        model = load_model(bestModelPath)
        print('got the model!')
    # the network is trained on data generatores and apply the callacks when the validation loss is not improving:
    # 1. early stop to training after n iteration
    # 2. reducing the learning rate after k iteration where k< n
    test_history = TestCallback(test_gen=test_gen,test_steps= (int(len_test/batch_size)) )

    modelcheckpoint = ModelCheckpoint(bestModelPath, monitor='loss', verbose=1, save_best_only=True, mode='auto', period=1)    
    
    history = model.fit_generator(
        steps_per_epoch=int(float(len_train) / float(batch_size * batch_epoch_ratio)),
        generator=train_gen,
        epochs=epochs,
        validation_data=validate_gen,
        validation_steps=int(float(len_valid) / float(batch_size)),
        callbacks=[EarlyStopping(monitor='val_loss', min_delta=0.001, patience=patience_es, ),
                   ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=patience_lr, min_lr=1e-8, verbose=1),
                   test_history, modelcheckpoint
                   ]
    )
    history_to_save = history.history
    history_to_save['test accuracy'] = test_history.test_acc
    history_to_save['test loss'] = test_history.test_loss

    model_name = ""
    for k, v in result.items():
        model_name = model_name + "_" + str(k) + "-" + str(v).replace(".", "d")
    model_path = os.path.join(res_path, model_name)
    try:
        pd.DataFrame(history_to_save).to_csv(model_path + "_train_results.csv")
        historyInDrivePath ='/gdrive/My Drive/THESIS/Data/' + str(dataset_name) + '_poseGatedNetTrainResults.csv'
        pd.DataFrame(history_to_save).to_csv(historyInDrivePath)
    except:
        pass
    result['validation loss'] = min(history.history['val_loss'])
    result['validation accuracy'] = max(history.history['val_acc'])
    result['last validation loss'] = history.history['val_loss'][-1]
    result['last validation accuracy'] = history.history['val_acc'][-1]

    result['train accuracy'] = max(history.history['acc'])
    result['train loss'] = min(history.history['loss'])
    result['last train accuracy'] = history.history['acc'][-1]
    result['last train loss'] = history.history['loss'][-1]

    result['test accuracy'] = max(test_history.test_acc)
    result['test loss'] = min(test_history.test_loss)
    result['last test accuracy'] = test_history.test_acc[-1]
    result['last test loss'] = test_history.test_loss[-1]

    result['final lr'] = history.history['lr'][-1]
    result['total epochs'] = len(history.history['lr'])
    return result


def get_generators(dataset_name, dataset_videos, datasets_frames, datasets_poses, fix_len, figure_size, force, classes=1, use_aug=False,
                   use_crop=True, crop_dark=None,use_fresh_data=True, e=None):
    
    crop_x_y = None
    if (crop_dark):
        crop_x_y = crop_dark[dataset_name]
    
    if use_fresh_data :
      train_path, valid_path, test_path, \
      train_y, valid_y, test_y, \
      avg_length = DatasetBuilder.createDataset(dataset_videos, datasets_frames, datasets_poses, fix_len, crop_x_y = crop_x_y, force=force, figure_shape = figure_size, e=e)
      trainingStuff = (train_path, valid_path, test_path, train_y, valid_y, test_y,avg_length)
      fileName = str(dataset_name) + 'Stuff.pickle'
      try:
        file_ = open(fileName, 'wb')
        pickle.dump(trainingStuff, file_)
        print('saved', fileName)
      except Exception as err:
        print(err)

    else :
      fileName = str(dataset_name) + 'Stuff.pickle'
      try:
        file_ = open(fileName, 'rb')
        trainingStuff = pickle.load(file_)
      except Exception as err:
        print(err)        
      
      train_path, valid_path, test_path, train_y, valid_y, test_y,avg_length = trainingStuff

    if test_data_integrity_flag:
      test_data_files(train_path, valid_path, test_path, train_y, valid_y, test_y,avg_length,fix_len,figure_size, force, classes=1, use_aug=False,
                   use_crop=True, crop_dark=None,use_fresh_data=True, e=None)
      return  None, None, None, None, None, None, None  
    
    if fix_len is not None:
        avg_length = fix_len
    
    len_train = len(train_path)
    len_test = len(test_path)
    len_valid = len(valid_path)
    print('prepared training stuff')
    train_gen = DatasetBuilder.data_generator(train_path, train_y, batch_size, figure_size, avg_length, use_aug=use_aug,
                                              use_crop=use_crop, crop_x_y=crop_x_y, classes=classes)
    print('prepared train gen')                                          
    validate_gen = DatasetBuilder.data_generator(valid_path, valid_y, batch_size, figure_size, avg_length,
                                                 use_aug=False, use_crop=False, crop_x_y=crop_x_y, classes=classes)
    print('prepared validate gen')
    test_gen = DatasetBuilder.test_generator(test_path, test_y, batch_size, figure_size, avg_length, use_aug=False, use_crop=False, crop_x_y=crop_x_y,
                                                  classes=classes)
    print('prepared test generator')
    print('prepared generators')

    return train_gen, validate_gen, test_gen, avg_length, len_train, len_valid, len_test


def test_data_files(train_path, valid_path, test_path, train_y, valid_y, test_y,avg_length,fix_len,figure_size, force, classes=1, use_aug=False,
                   use_crop=True, crop_dark=None,use_fresh_data=True, e=None):
    
    crop_x_y = None
    if (crop_dark):
        crop_x_y = crop_dark[dataset_name]
    
    
    if fix_len is not None:
        avg_length = fix_len
    
    len_train = len(train_path)
    len_test = len(test_path)
    len_valid = len(valid_path)
    print('testing training files...')
    train_gen = DatasetBuilder.test_data_integrity(train_path, train_y, batch_size, figure_size, avg_length, use_aug=use_aug,
                                              use_crop=use_crop, crop_x_y=crop_x_y, classes=classes)
    print('testing validation files...')                                          
    validate_gen = DatasetBuilder.test_data_integrity(valid_path, valid_y, batch_size, figure_size, avg_length,
                                                 use_aug=False, use_crop=False, crop_x_y=crop_x_y, classes=classes)
    print('testing testing files...')
    test_gen = DatasetBuilder.test_data_integrity(test_path, test_y, batch_size, figure_size, avg_length, use_aug=False, use_crop=False, crop_x_y=crop_x_y,
                                                  classes=classes)
    




def hyper_tune_network(dataset_name, epochs, batch_size, batch_epoch_ratio, figure_size, initial_weights, lstm,
                       cnns_arch,
                       learning_rates, optimizers, cnn_train_types, dropouts, classes, use_augs, fix_lens):
    """ the function train several networks parameters in a loop and select the best architechture to the next evaluation"""
    results = []

    best_accuracy = 0.0
    best_loss = 10.0
    # static params for tunning
    params_to_train = dict(dataset_name=dataset_name, epochs=epochs, batch_size=batch_size,
                           batch_epoch_ratio=batch_epoch_ratio, initial_weights=initial_weights, size=figure_size,
                           pre_weights=weights, lstm_conf=lstm, classes=classes, patience_es=5, patience_lr=3)

    # the tunning is not evaluation all possible combinations
    # given the importance order of the hyperparams, in each iteraction we choose the best performing parmaters
    exp_params_order = ['cnn_arch', 'learning_rate', 'seq_len', 'use_aug', 'dropout',
                        'cnn_train_type']  # 'cnn_arch','learning_rate','fix_len','use_aug','dropout', 'optimizer','optimizer',
    #

    best_params_train = dict(optimizer=optimizers[0], learning_rate=learning_rates[0],
                             cnn_train_type=cnn_train_types[0], cnn_arch=cnns_arch.values()[0],
                             dropout=dropouts[0])
    exp_params_train = dict(optimizer=optimizers[1:], learning_rate=learning_rates[1:],
                            cnn_train_type=cnn_train_types[1:], dropout=dropouts[1:],
                            cnn_arch=cnns_arch.values())

    best_params_data = dict(use_aug=use_augs[0], seq_len=fix_lens[0])
    exp_params_data = dict(use_aug=use_augs[1:], seq_len=fix_lens[1:])

    for exp_param in exp_params_order:
        temp_param = dict(best_params_train)
        temp_param_data = dict(best_params_data)
        if exp_param in exp_params_data:
            exp_params_ = exp_params_data
        else:
            exp_params_ = exp_params_train
        for param in exp_params_[exp_param]:
            if exp_param in best_params_data:
                temp_param_data[exp_param] = param
            else:
                temp_param[exp_param] = param

            print(temp_param_data)
            print(temp_param)
            params_to_train['train_gen'], params_to_train['validate_gen'], params_to_train['test_x'], \
            params_to_train['test_y'], params_to_train['seq_len'], params_to_train['len_train'], \
            params_to_train['len_valid'] = get_generators(dataset_name, datasets_videos[dataset_name], datasets_frames,
                                                          temp_param_data['seq_len'],
                                                          figure_size, use_aug=temp_param_data['use_aug'], force=force,
                                                          classes=classes)

            params_to_train.update(temp_param)
            result = train_eval_network(**params_to_train)
            result.update(temp_param_data)
            print(result)
            results.append(result)
            if result['test accuracy'] >= best_accuracy:  # and result['test loss'] <= best_loss :
                best_accuracy = result['test accuracy']
                best_loss = result['test loss']
                if exp_param in best_params_data:
                    best_params_data[exp_param] = param
                else:
                    best_params_train[exp_param] = param
                print("best accuracy update " + str(best_accuracy))
    best_params_train.update(best_params_data)
    return best_params_train, results


# static parameter for the netwotk
datasets_videos = dict(
    hocky=dict(hocky="data/raw_videos/HockeyFights"),
    #violentflow=dict(violentflow="data/raw_videos/violentflow"),
    #movies=dict(movies="data/raw_videos/movies")
)

crop_dark = dict(
    hocky=(18, 48)
    #violentflow=None,
    #movies=None
)

datasets_frames = "data/raw_frames"
datasets_poses = "data/raw_poses"
res_path = "results"
figure_size = 224
# split_ratio = 0.1
batch_size = 2
# batch_epoch_ratio = 0.5 #double the size because we use augmentation
fix_len = 20
initial_weights = 'glorot_uniform'
weights = 'imagenet'
force = True
lstm = (ConvLSTM2D, dict(filters=256, kernel_size=(3, 3), padding='same', return_sequences=False))
classes = 1

# hyper parameters for tunning the network
cnns_arch = dict(ResNet50=ResNet50, InceptionV3=InceptionV3, VGG19=VGG19)  #
learning_rates = [1e-4, 1e-3]
use_augs = [True, False, ]
fix_lens = [20, 10]
optimizers = [(RMSprop, {}), (Adam, {})]
dropouts = [0.0, 0.5]
cnn_train_types = ['retrain', 'static']


results = []
cnn_arch, learning_rate, optimizer, cnn_train_type, dropout, use_aug, fix_len = ResNet50, 0.0001, (Adam, {}), 'retrain', 0.0, True, 20






import pickle
###### use fresh data = False when we have raw frames ready for us
use_fresh_data = False # SET USE_FRESH_DATA HERE!
######
test_data_integrity_flag = False
######
use_new_model = False
######


e = None
if use_fresh_data == True:
  from tf_pose.estimator import TfPoseEstimator
  from tf_pose.networks import get_graph_path, model_wh
  e = TfPoseEstimator(get_graph_path('mobilenet_thin'))


# apply best architechture on all datasets with more epochs
for dataset_name, dataset_videos in datasets_videos.items():
    print('--------------')
    print(str(dataset_name))
    print('--------------')
    
    train_gen, validate_gen, test_gen, seq_len, len_train, len_valid, len_test = get_generators(dataset_name,
                                                                                            dataset_videos,
                                                                                            datasets_frames, datasets_poses, fix_len,
                                                                                            figure_size,
                                                                                            force=force,
                                                                                            classes=classes,
                                                                                            use_aug=use_aug,
                                                                                            use_crop=True,
                                                                                            crop_dark=crop_dark,use_fresh_data = use_fresh_data, e=e)

    print('finish training data preparation for',dataset_name)
        
    
    #continue #debug
    result = train_eval_network(epochs=10, dataset_name=dataset_name, train_gen=train_gen, validate_gen=validate_gen,
                                test_gen = test_gen, seq_len=seq_len, batch_size=batch_size,
                                batch_epoch_ratio=0.5, initial_weights=initial_weights, size=figure_size,
                                cnn_arch=cnn_arch, learning_rate=learning_rate,
                                optimizer=optimizer, cnn_train_type=cnn_train_type,
                                pre_weights=weights, lstm_conf=lstm, len_train=len_train, len_valid=len_valid, len_test = len_test,
                                dropout=dropout, classes=classes)
    #debug
    results.append(result)
    pd.DataFrame(results).to_csv("results_datasets.csv")
    print(result)
pd.DataFrame(results).to_csv("results_march24.csv")

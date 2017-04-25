from json import load
from keras.callbacks import ModelCheckpoint, Callback
from keras.utils import np_utils
from keras.layers import Input, Dense
from keras.models import Model, load_model
import numpy as np
from feature_extractor import FeatureExtractor
from data_gatherer import get_elo_from_division_request
import matplotlib.pyplot as plt
import os

'''

Trains or prints overall statistics about a section title-detecting neural network. See command line arguments for usage.

'''



def get_new_model(num_input_features):
    feature_input = Input(shape = (num_input_features,), dtype = 'float32')
    # The number of nodes in these dense layers is somewhat arbitrary and could be tweaked
    # for slight gains.
    y = Dense(1000, activation = 'relu')(feature_input)
    y = Dense(100, activation='relu')(y)
    preds = Dense(1, activation='relu')(y)
    model = Model(feature_input, preds)
    model.compile(loss='mean_squared_error',
                  optimizer='rmsprop',
                  metrics=['acc'])

    return model

def get_data_split(data, split_fraction):
    nb_validation_samples = int(split_fraction * data.shape[0])
    data_train = data[:nb_validation_samples]
    data_val = data[nb_validation_samples:]
    return (data_train, data_val)

def load_all_json(folder):
    for filename in os.listdir(folder):
        if os.path.isdir(filename):
            for (path, document) in load_all_txt(folder):
                yield (folder + path, document)
        elif filename.lower().endswith('.json'):
            with open(os.path.join(folder, filename), 'r') as fp:
                json_document = load(fp)
                yield (filename, json_document)





def get_data_and_labels(games_directory, divisions_directory):
    labels = []
    feature_vector = []
    feature_extractor = FeatureExtractor()

    # games_directory = os.path.join(labeled_documents_path, "games")
    # divisions_directory = os.path.join(labeled_documents_path, "summoner_divisions")

    json_paths_and_docs = load_all_json(games_directory)
    num_missing = 0
    # Go through them all and create our feature vector and label set.
    for (game_path, json_document) in json_paths_and_docs:
        _, match_id = os.path.split(game_path)
        try:
            with open(os.path.join(divisions_directory, match_id), 'r') as fp:
                division_summary_json = load(fp)
                labels.append([get_elo_from_division_request(division_summary_json)])
        except IOError:
            num_missing += 1
            continue
        
        if len(feature_vector) % 100 == 0:
            print len(feature_vector)

        feature_vector.append(feature_extractor.get_feature_vector(json_document))

        # if len(feature_vector) > 100:
        #     break

    print num_missing

    feature_vector = np.asarray(feature_vector)
    labels = np.asarray(labels)
    print 'Found %s texts.' % len(labels)
    return (feature_vector, labels)


if __name__ == '__main__':
    import argparse
        
    parser = argparse.ArgumentParser(description='Build or evaluate NN-based title prediction models. By default, builds a new model.')

    parser.add_argument('--input', type = str, nargs = '?', default = "data/", 
        help= 'Directory of the input documents or document to evaluate or train on')

    parser.add_argument('--debug', type = bool, nargs = '?',
        help ='a boolean value to turn on debugging mode otherwise default to False', 
        default = False)

    parser.add_argument('--model_dir', type = str, nargs = '?', default = "models/title_model_15.h5", help = "Directory to either load the model from or save the model to.")
    parser.add_argument('--load_model', action = 'store_true')

    args = parser.parse_args()
    labeled_documents_path = args.input
    model_dir = args.model_dir

    VALIDATION_SPLIT = 0.2
    TEST_SPLIT = 0.1

    games_directory = os.path.join(labeled_documents_path, "games")
    divisions_directory = os.path.join(labeled_documents_path, "summoner_divisions")

    # First load the data from the given set of labeled documents.
    feature_vector, labels = get_data_and_labels(games_directory, divisions_directory)

    print 'Shape of data tensor:', feature_vector.shape
    print 'Shape of label tensor:', labels.shape

    indices = np.arange(feature_vector.shape[0])
    np.random.shuffle(indices)
    feature_vector = feature_vector[indices]
    labels = labels[indices]

    # split the data into a training set and a validation set
    x_train, x_val_and_test = get_data_split(feature_vector, 1 - VALIDATION_SPLIT - TEST_SPLIT)
    y_train, y_val_and_test = get_data_split(labels, 1 - VALIDATION_SPLIT - TEST_SPLIT)
    x_val, x_test = get_data_split(x_val_and_test, VALIDATION_SPLIT / (VALIDATION_SPLIT + TEST_SPLIT))
    y_val, y_test = get_data_split(y_val_and_test, VALIDATION_SPLIT / (VALIDATION_SPLIT + TEST_SPLIT))

    if args.load_model:
        print 'wtf'
        model = load_model(model_dir)
    else:
        num_features = feature_vector.shape[1]
        model = get_new_model(num_features)
        checkpointer = ModelCheckpoint(filepath=model_dir, verbose=1, save_best_only=True)
        model.fit(x_train, y_train, validation_data=(x_val, y_val), nb_epoch=75, batch_size=128)
        predictions = model.predict(x_test)
        
        short_predictions = predictions[:200]
        short_test = y_test[:200]
        print [i for i in zip(short_predictions, short_test)]
        print 'Mean squared error: %s' % ((predictions - y_test)**2).mean()

        plt.scatter(y_test, predictions)
        plt.xlim(500, 3000)
        plt.xlabel('Actual elo')
        plt.ylim(500, 3000)
        plt.ylabel('Predicted elo')

        plt.title('Predictions vs. actual elo using pick/ban, items, cs, and wards')

        plt.plot([800, 2700], [800, 2700], color='k', linestyle='-', linewidth=2)

        plt.show()
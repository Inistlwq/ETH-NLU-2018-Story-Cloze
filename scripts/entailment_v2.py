"""
Credits to
- Matteo Pagliardini, Prakhar Gupta, Martin Jaggi,
    Unsupervised Learning of Sentence Embeddings using Compositional n-Gram Features NAACL 2018,
    https://arxiv.org/abs/1703.02507
- A large annotated corpus for learning natural language inference,
    _Samuel R. Bowman, Gabor Angeli, Christopher Potts, and Christopher D. Manning_,
    https://nlp.stanford.edu/pubs/snli_paper.pdf.
"""
import datetime
import os
import random

import keras
import sent2vec
import numpy as np
from utils import SNLIDataloader
from nltk import word_tokenize


class Preprocess:
    def __init__(self, sent2vec):
        self.sent2vec = sent2vec

    def __call__(self, line):
        # label = [entailment, neutral, contradiction]
        label = 1
        if line['gold_label'] == 'contradiction':
            label = 0
        elif line['gold_label'] == 'neutral':
            label = 0
        sentence1 = list(self.sent2vec.embed_sentence(' '.join(word_tokenize(line['sentence1']))))
        sentence2 = list(self.sent2vec.embed_sentence(' '.join(word_tokenize(line['sentence2']))))
        output = [label, sentence1, sentence2]
        return output


class PreprocessTest:
    """
    Preprocess to apply to the dataset
    """

    def __init__(self, sent2vec_model):
        self.sent2vec_model = sent2vec_model

    def __call__(self, word_to_index, sentence):
        sentence = self.sent2vec_model.embed_sentence(' '.join(sentence))
        return sentence


def output_fn(_, batch):
    batch = np.array(batch)
    return [np.array(list(batch[:, 1])), np.array(list(batch[:, 2]))], np.array(list(batch[:, 0]))


def output_fn_test(data):
    batch = np.array(data.batch)
    last_sentences = batch[:, 3, :]
    ending_1 = batch[:, 4, :]
    ending_2 = batch[:, 5, :]
    endings = ending_2[:]
    correct_ending = data.label
    label = np.array(correct_ending) - 1
    final_label = []
    # correct ending if 1 --> if 2 true get 2 - 1 = 1, if 1 true get 1 - 1 = 0
    if random.random() > 0.5:
        endings = ending_1[:]
        label = 1 - label
    for b in range(len(label)):
        final_label.append([1, 0, 0] if label[b] == 1 else [0, 0.5, 0.5])
    # Return what's needed for keras
    return [last_sentences, endings], np.array(final_label)


def model(config):
    dense_layer_1 = keras.layers.Dense(500, activation='relu')
    dense_layer_2 = keras.layers.Dense(100, activation='relu')
    dense_layer_3 = keras.layers.Dense(1, activation='sigmoid')

    sentence_1 = keras.layers.Input(shape=(config.sent2vec.embedding_size,))
    sentence_2 = keras.layers.Input(shape=(config.sent2vec.embedding_size,))
    # Graph
    inputs = keras.layers.Concatenate()([sentence_1, sentence_2])
    # inputs = sentiments
    output = keras.layers.Dropout(0.3)(dense_layer_1(inputs))
    output = keras.layers.Dropout(0.3)(dense_layer_2(output))
    output = dense_layer_3(output)

    # Model
    model = keras.models.Model(inputs=[sentence_1, sentence_2], outputs=[output])
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=['accuracy'])
    return model


def main(config):
    assert config.sent2vec.model is not None, "Please add sent2vec_model config value."
    sent2vec_model = sent2vec.Sent2vecModel()
    sent2vec_model.load_model(config.sent2vec.model)

    preprocess_fn = Preprocess(sent2vec_model)

    train_set = SNLIDataloader('data/snli_1.0/snli_1.0_train.jsonl')
    train_set.set_preprocess_fn(preprocess_fn)
    train_set.set_output_fn(output_fn)
    dev_set = SNLIDataloader('data/snli_1.0/snli_1.0_dev.jsonl')
    dev_set.set_preprocess_fn(preprocess_fn)
    dev_set.set_output_fn(output_fn)
    test_set = SNLIDataloader('data/snli_1.0/snli_1.0_test.jsonl')

    generator_training = train_set.get_batch(config.batch_size, config.n_epochs)
    generator_dev = dev_set.get_batch(config.batch_size, config.n_epochs)

    keras_model = model(config)

    verbose = 0 if not config.debug else 1
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Callbacks
    tensorboard = keras.callbacks.TensorBoard(log_dir='./logs/' + timestamp + '-entailmentv2/', histogram_freq=0,
                                              batch_size=config.batch_size,
                                              write_graph=False,
                                              write_grads=True)

    model_path = os.path.abspath(
        os.path.join(os.curdir, './builds/' + timestamp))
    model_path += '-entailmentv2_checkpoint_epoch-{epoch:02d}.hdf5'

    saver = keras.callbacks.ModelCheckpoint(model_path,
                                            monitor='val_acc', verbose=verbose, save_best_only=True)

    keras_model.fit_generator(generator_training, steps_per_epoch=100,
                              epochs=config.n_epochs,
                              verbose=verbose,
                              validation_data=generator_dev,
                              validation_steps=len(test_set) / config.batch_size,
                              callbacks=[tensorboard, saver])


def test(config, testing_set):
    assert config.sent2vec.model is not None, "Please add sent2vec_model config value."
    sent2vec_model = sent2vec.Sent2vecModel()
    sent2vec_model.load_model(config.sent2vec.model)

    preprocess_fn = PreprocessTest(sent2vec_model)
    testing_set.set_preprocess_fn(preprocess_fn)

    testing_set.set_output_fn(output_fn_test)

    generator_testing = testing_set.get_batch(config.batch_size, config.n_epochs, random=True)

    keras_model = keras.models.load_model(
        './builds/leonhard/2018-05-18 18:31:30-entailmentv2_checkpoint_epoch-708.hdf5')

    verbose = 0 if not config.debug else 1

    # test_batch = next(generator_testing)
    loss = keras_model.evaluate_generator(generator_testing, steps=len(testing_set) / config.batch_size,
                                          verbose=verbose)
    print(loss)
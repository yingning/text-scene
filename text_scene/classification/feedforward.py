import os
import sys
import numpy as np
from keras.models import Sequential, Model
from keras.layers import Dense, Dropout, Activation
from keras.layers import Flatten, Lambda, Merge, merge
from keras.layers import Embedding, Input, BatchNormalization
from keras.layers.advanced_activations import LeakyReLU, PReLU, ELU
from keras.regularizers import l2
from keras.optimizers import Adam
from keras.callbacks import EarlyStopping
from keras import backend as K

class FeedforwardNN(object):
    def __init__(self, vocab_size, nb_labels, emb_dim, maxlen, layer_sizes,
                 embedding_weights, pool_mode='max', activation='relu'):
        self.nb_labels = nb_labels
        sentence_input = Input(shape=(maxlen,), dtype='int32')
        x = Embedding(input_dim=vocab_size+1,
                      output_dim=emb_dim,
                      input_length=maxlen,
                      weights=[embedding_weights],
                      dropout=0.2)
        x = x(sentence_input)
        if pool_mode == 'sum':
            pool = Lambda(lambda x: K.sum(x, axis=1), output_shape=(emb_dim,))
        elif pool_mode == 'max':
            pool = Lambda(lambda x: K.max(x, axis=1), output_shape=(emb_dim,))
        elif pool_mode == 'mean':
            pool = Lambda(lambda x: K.mean(x, axis=1), output_shape=(emb_dim,))
        else: # concat
            pool = Flatten()
        pool_out = Dropout(0.5)(pool(x))
        hidden_layers = []
        prev_layer = pool_out
        for layer_size in layer_sizes[:-1]:
            hidden_in = Dense(layer_size)(prev_layer)
            hidden_bn = BatchNormalization()(hidden_in)
            if activation == 'relu':
                hidden_activation = Activation('relu')(hidden_bn)
            elif activation == 'tanh':
                hidden_activation = Activation('tanh')(hidden_bn)
            elif activation == 'prelu':
                hidden_activation = PReLU()(hidden_bn)
            elif activation == 'leakyrelu':
                hidden_activation = LeakyReLU()(hidden_bn)
            else: #ELU
                hidden_activation = ELU()(hidden_bn)
            hidden_out = Dropout(0.5)(hidden_activation)
            hidden_layers.append(hidden_out)
            prev_layer = hidden_out
        final_hidden_in = Dense(layer_sizes[-1])(hidden_layers[-1])
        if activation == 'relu':
            final_hidden_activation = Activation('relu')(final_hidden_in)
        elif activation == 'tanh':
            final_hidden_activation = Activation('tanh')(final_hidden_in)
        elif activation == 'prelu':
            final_hidden_activation = PReLU()(final_hidden_in)
        elif activation == 'leakyrelu':
            final_hidden_activation = LeakyReLU()(final_hidden_in)
        else: #ELU
            final_hidden_activation = ELU()(final_hidden_in)
        if self.nb_labels == 2:
            out = Dense(1, activation='sigmoid')
        else:
            out = Dense(nb_labels, activation='softmax')
        out = out(final_hidden_activation)
        self.model = Model(input=sentence_input, output=out)

class FastText(object):
    def __init__(self, vocab_size, nb_labels, emb_dim, maxlen, layer_sizes,
                 embedding_weights, pool_mode='max', activation='relu'):
        self.nb_labels = nb_labels
        sentence_input = Input(shape=(maxlen,), dtype='int32')
        x = Embedding(input_dim=vocab_size+1,
                      output_dim=emb_dim,
                      input_length=maxlen,
                      weights=None)
        x = x(sentence_input)
        pool = Lambda(lambda x: K.mean(x, axis=1), output_shape=(emb_dim,))
        pool_out = pool(x)
        if self.nb_labels == 2:
            out = Dense(1, activation='sigmoid')
        else:
            out = Dense(nb_labels, activation='softmax')
        out = out(pool_out)
        self.model = Model(input=sentence_input, output=out)

def train_and_test_model(nn, X_train, y_train, X_test, y_test,
                         batch_size, nb_epoch,
                         lr, beta_1, beta_2, epsilon,
                         val_split=0.10):
    adam = Adam(lr=lr, beta_1=beta_1, beta_2=beta_2, epsilon=epsilon)
    if nn.nb_labels == 2:
        nn.model.compile(loss='binary_crossentropy',
                      optimizer=adam,
                      metrics=['accuracy'])
    else:
        nn.model.compile(loss='categorical_crossentropy',
                      optimizer=adam,
                      metrics=['accuracy'])
    early_stopping = EarlyStopping(monitor='val_loss', patience=5,
                                   verbose=0, mode='auto')
    nn.model.fit(X_train, y_train, nb_epoch=nb_epoch,
                 batch_size=batch_size,
                 validation_split=val_split,
                 callbacks=[early_stopping])
    score, acc = nn.model.evaluate(X_test, y_test, batch_size=64)
    return nn, acc

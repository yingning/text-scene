import os
import sys
import time
import numpy as np
from collections import Counter
from keras.utils.np_utils import to_categorical, probas_to_classes
from keras.utils.layer_utils import print_summary
from sklearn.cross_validation import StratifiedKFold

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from preprocessing.data_utils import (
    load_bin_vec,
    sentences_df,
    load_dataset,
    add_unknown_words
)
from corpus_stats.frequency import print_label_frequencies
from cnn import create_model, train_and_test_model
from paths import SENTENCES_CSV


# Model hyperparameters
emb_dim = 300
filter_hs = [5,10,15]
nb_filters = 150
dropout_p = [0.2,0.2] # [input, softmax]
trainable_embeddings = True
pretrained_embeddings = True

# Training parameters (Adam optimizer)
batch_size = 128
nb_epoch = 15
lr = 0.001
beta_1 = 0.9
beta_2 = 0.999
epsilon = 1e-08

def add_unknown_words(word_vecs, vocab, k=300):
    added = 0
    for word in vocab:
        if word not in word_vecs:
            word_vecs[word] = np.random.uniform(-0.25,0.25,k)
            added += 1
    word_vecs['<unk>'] = np.random.uniform(-0.25,0.25,k)
    print "Added %i unknown words to word vectors." % added

def train(model_type='parallel', label_set='full', drop_unk=False,
          word_vecs=None, setup_only=False):
    print "Loading data..."
    df = sentences_df(SENTENCES_CSV, labels=label_set, drop_unk=drop_unk)
    X, y, word2idx, l_enc = load_dataset(df, pad=True)
    print "X shape:", X.shape
    y_orig = y
    y_binary = to_categorical(y)
    labels = np.unique(y_orig)
    nb_labels = labels.shape[0]
    if drop_unk:
        label_set_str = label_set + ' (-unk)'
    else:
        label_set_str = label_set
    print "Number of labels: %i [%s]" % (nb_labels, label_set_str)
    if nb_labels > 2:
        y = y_binary
    maxlen = X.shape[1]
    vocab_size = len(word2idx) + 1 # 0 masking
    if pretrained_embeddings is True:
        word_vectors = load_bin_vec(word_vecs, word2idx)
        add_unknown_words(word_vectors, word2idx)
        embedding_weights = np.zeros((vocab_size+1, emb_dim))
        for word, index in word2idx.items():
            embedding_weights[index,:] = word_vectors[word]
    else:
        embedding_weights = None
    print "Data loaded."

    if setup_only:
        cnn = create_model(vocab_size, nb_labels, emb_dim, maxlen,
                           embedding_weights, filter_hs, nb_filters,
                           dropout_p, trainable_embeddings,
                           pretrained_embeddings, model_type=model_type)
        return {'X': X,
                'y': y,
                'word2idx': word2idx,
                'l_enc': l_enc,
                'y_binary': y_binary,
                'labels': labels,
                'nb_labels': nb_labels,
                'maxlen': maxlen,
                'emb_dim': emb_dim,
                'vocab_size': vocab_size,
                'embedding_weights': embedding_weights,
                'cnn': cnn}

    params = [('filter_hs',filter_hs), ('nb_filters',nb_filters),
              ('dropout_p',dropout_p),
              ('trainable_embeddings',trainable_embeddings),
              ('pretrained_embeddings',pretrained_embeddings),
              ('batch_size',batch_size), ('nb_epoch',nb_epoch),
              ('lr',lr), ('beta_1',beta_1), ('beta_2',beta_2),
              ('epsilon',epsilon)]
    print "\nModel type: %s" % model_type
    for (name, value) in params:
        print name + ':', value

    skf = StratifiedKFold(y_orig, n_folds=10, shuffle=True, random_state=0)
    cv_scores = []
    for i, (train, test) in enumerate(skf):
        start_time = time.time()
        cnn = None
        cnn = create_model(vocab_size,
                           nb_labels,
                           emb_dim,
                           maxlen,
                           embedding_weights,
                           filter_hs,
                           nb_filters,
                           dropout_p,
                           trainable_embeddings,
                           pretrained_embeddings,
                           model_type=model_type)
        if i == 0:
            print_summary(cnn.model.layers)

        acc = train_and_test_model(cnn, X[train], y[train], X[test], y[test],
                                   batch_size, nb_epoch,
                                   lr, beta_1, beta_2, epsilon)
        cv_scores.append(acc)
        train_time = time.time() - start_time
        print('\nLabel frequencies in y[test]')
        print_label_frequencies((y_orig[test], l_enc))
        y_pred = cnn.model.predict(X[test])
        y_pred = probas_to_classes(y_pred)
        c = Counter(y_pred)
        total = float(len(y_pred))
        print('\nLabel frequencies in predict(y[test])')
        for label, count in c.most_common():
            print l_enc.inverse_transform(label), count, count / total
        print "fold %i/10 - time: %.2f s - acc: %.4f on %i samples" % \
            (i+1, train_time, acc, len(test))
    print "Avg cv accuracy: %.4f" % np.mean(cv_scores)

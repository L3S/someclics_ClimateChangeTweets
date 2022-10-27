import tensorflow as tf
from keras import backend as k
from keras import layers
from keras.layers.core import Lambda
import numpy as np 
from numpy import asarray,zeros, array
import pandas as pd
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from keras.layers import LSTM,Dropout,Bidirectional,Input, Embedding, Dense,Concatenate,Flatten, Multiply,Average
from keras.models import Model
from keras.layers.merge import concatenate
from keras.utils import to_categorical
from keras.engine import Layer
from keras.optimizers import Adam
from sklearn.metrics import accuracy_score,classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder
from keras import optimizers,regularizers
import random,statistics,json
from sklearn.model_selection import StratifiedKFold
from sklearn.utils import resample

def attentionScores(var):
    Q_t,K_t,V_t=var[0],var[1],var[2]
    scores = tf.matmul(Q_t, K_t, transpose_b=True)
    distribution = tf.nn.softmax(scores)
    scores=tf.matmul(distribution, V_t)
    return scores

def attentionScoresIRA(var):
    Q_t,K_t,V_t,Q_e,K_e,V_e=var[0],var[1],var[2],var[3],var[4],var[5]
    score_t = tf.matmul(Q_t, K_e, transpose_b=True)
    distribution_t = tf.nn.softmax(score_t)
    scores_t=tf.matmul(distribution_t, V_t)
    score_e = tf.matmul(Q_e, K_t, transpose_b=True)
    distribution_e = tf.nn.softmax(score_e)
    scores_e=tf.matmul(distribution_e, V_e)
    IRAScores=Concatenate()([scores_t,scores_e])
    return IRAScores

#####
def attentionScoresIRA1(var):
    Q_t,K_t,V_t,Q_e,K_e,V_e=var[0],var[1],var[2],var[3],var[4],var[5]
    score_t = tf.matmul(Q_t, K_e, transpose_b=True)
    distribution_t = tf.nn.softmax(score_t)
    scores_e=tf.matmul(distribution_t, V_e)
    score_e = tf.matmul(Q_e, K_t, transpose_b=True)
    distribution_e = tf.nn.softmax(score_e)
    scores_t=tf.matmul(distribution_e, V_t)
    IRAScores=Concatenate()([scores_t,scores_e])
    return IRAScores

####### oversampling minor class ######
def create_resample(train_sequence,train_sequence_topic,train_enc,train_enc_senti):
    df = pd.DataFrame(list(zip(train_sequence,train_sequence_topic,train_enc,train_enc_senti)), columns =['text','topic','pol','sent'],index=None)
    blv=(df[df['pol'] == 0])
    print("len blv",len(blv))
    deny=(df[df['pol'] == 1])
    print("len deny",len(deny))
    upsampled1 = resample(deny,replace=True, # sample with replacement
                          n_samples=len(blv), # match number in majority class
                          random_state=27)

    upsampled = pd.concat([blv,upsampled1])
    upsampled=upsampled.sample(frac=1)
    print("After oversample train data : ",len(upsampled))
    print("After oversampling, instances of tweet act classes in oversampled data :: ",upsampled.pol.value_counts())

    train_data=upsampled
    train_sequence=[]
    train_sequence_topic=[]
    train_enc=[]
    train_enc_senti=[]
   
    for i in range(len(train_data)):
        train_sequence.append(train_data.text.values[i])
        train_sequence_topic.append((train_data.topic.values[i]))
        train_enc.append(train_data.pol.values[i])
        train_enc_senti.append(train_data.sent.values[i])


    return train_sequence,train_sequence_topic,train_enc,train_enc_senti



############## if you want to test on 80-20% split (therefore train and test split) ##########

########### train data 
train_data=pd.read_csv("../../data/train.csv", delimiter=";", na_filter= False) 
print("train_data :: ",len(train_data))

train_senti=[]
train_stance=[]
train_id=[]
train_topic=[]
train_text=[]

for i in range(len(train_data)):
    train_id.append(train_data.tid.values[i])
    train_text.append(train_data.text.values[i])
    train_senti.append((train_data.sent.values[i]))
    train_stance.append(train_data.pol.values[i])
    train_topic.append(train_data.topic.values[i])

print("train_stance np unique:::",np.unique(train_stance,return_counts=True))

########### test_data
test_data=pd.read_csv("../../data/test.csv", delimiter=";", na_filter= False) 
print("test_data :: ",len(test_data))

test_text=[]
test_senti=[]
test_stance=[]
test_id=[]
test_topic=[]

for i in range(len(test_data)):
    id_=str(test_data.tid.values[i])
    sent=str(test_data.sent.values[i])
    # if sent !="neutral" :
    test_id.append(test_data.tid.values[i])
    test_text.append(test_data.text.values[i])
    test_senti.append((test_data.sent.values[i]))
    test_stance.append(test_data.pol.values[i])
    test_topic.append(test_data.topic.values[i])

print("test_stance np unique:::",np.unique(test_stance,return_counts=True))

########### converting stance labels into categorical labels ########
label_encoder=LabelEncoder()
final_lbls=train_stance+test_stance
values=array(final_lbls)
total_integer_encoded=label_encoder.fit_transform(values)

train_enc_stance=total_integer_encoded[0:len(train_text)]
test_enc_stance=total_integer_encoded[len(train_text):]
total_integer_encoded=to_categorical(total_integer_encoded)

train_stance=total_integer_encoded[0:len(train_text)]
test_stance=total_integer_encoded[len(train_text):]


########### converting senti labels into categorical labels ########
label_encoder=LabelEncoder()
final_lbls=train_senti+test_senti
values=array(final_lbls)
total_integer_encoded=label_encoder.fit_transform(values)

train_enc_senti=total_integer_encoded[0:len(train_text)]
test_enc_senti=total_integer_encoded[len(train_text):]
total_integer_encoded=to_categorical(total_integer_encoded)

train_senti=total_integer_encoded[0:len(train_text)]
test_senti=total_integer_encoded[len(train_text):]

########## converting text modality into sequence of vectors ############
total_text= train_text+test_text
total_text = [x.lower() for x in total_text] 
####3 need to check
MAX_SEQ=150
tokenizer = Tokenizer()
tokenizer.fit_on_texts(total_text)
total_sequence = tokenizer.texts_to_sequences(total_text)
padded_docs = pad_sequences(total_sequence, maxlen=MAX_SEQ, padding='post')

train_sequence=padded_docs[0:len(train_text)] #text
test_sequence=padded_docs[len(train_text):]
vocab_size = len(tokenizer.word_index) + 1

print("downloading ###")
embedding_matrix= np.load("../../embedding_matrix/embed_matrix_BERT.npy")
print("embedding matrix ****************",embedding_matrix.shape)
print("non zeros bert :",sum(np.all(embedding_matrix, axis=1)))


#############topic embedding vector ###########

total_topic= train_topic+test_topic
total_topic = [x.lower() for x in total_topic] 
####3 need to check
MAX_SEQ=50
tokenizer = Tokenizer()
tokenizer.fit_on_texts(total_topic)
total_sequence_topic = tokenizer.texts_to_sequences(total_topic)
# padded_docs = np.load("../../embedding_matrix/padded_docs_glove_10sep.npy")

padded_docs_topic = pad_sequences(total_sequence_topic, maxlen=50, padding='post')


print("padded_docs topic:::::::",padded_docs_topic[:2])

train_sequence_topic=padded_docs_topic[0:len(train_text)] #text
test_sequence_topic=padded_docs_topic[len(train_text):]
vocab_size_topic = len(tokenizer.word_index) + 1

print("downloading topic ###",train_sequence_topic.shape)
embedding_matrix_topic= np.load("../../embedding_matrix/embed_matrix_BERT_topic.npy")
print("embedding matrix topic ****************",embedding_matrix_topic.shape)

train_stance=np.array(train_stance)
test_stance=np.array(test_stance)
train_senti=np.array(train_senti)
test_senti=np.array(test_senti)

MAX_LENGTH=150


#######data for K-fold #########

total_labels_stance= np.vstack((train_stance,test_stance))
total_labels_senti= np.vstack((train_senti,test_senti))
total_sequence=np.vstack((train_sequence,test_sequence))
total_sequence_topic=np.vstack((train_sequence_topic,test_sequence_topic))

total_labels_stance_enc = np.argmax(total_labels_stance, axis=1)
list_acc_stance,list_acc_senti=[],[]
list_f1_stance,list_f1_senti=[],[]

kf=StratifiedKFold(n_splits=5, random_state=None,shuffle=False)
fold=0
results=[]
for train_index,test_index in kf.split(total_sequence,total_labels_stance_enc):
    print("K FOLD ::::::",fold)
    fold=fold+1
    
    ############## Stance inputs #############
    input1 = Input (shape = (150, ))
    input_text = Embedding(vocab_size, 768, weights=[embedding_matrix], input_length=150, name='text_share_embed')(input1)
    lstm_text = Bidirectional(LSTM(100, name='lstm_inp1', activation='tanh',dropout=.2,kernel_regularizer=regularizers.l2(0.07)))(input_text)
    text_final = Dense(100, activation="relu")(lstm_text)
    Q_t= Dense(100, activation="relu")(text_final)
    K_t= Dense(100, activation="relu")(text_final)
    V_t= Dense(100, activation="relu")(text_final)
    IA_text=Lambda(attentionScores)([Q_t,K_t,V_t])

    input2 = Input (shape = (50, ))
    input_topic = Embedding(vocab_size_topic, 768, weights=[embedding_matrix_topic], input_length=50, name='topic_share_embed')(input2)
    lstm_topic = Bidirectional(LSTM(100, name='lstm_inp2', activation='tanh',dropout=.2,kernel_regularizer=regularizers.l2(0.07)))(input_topic)
    topic_final = Dense(100, activation="relu")(lstm_topic)
    Q_e= Dense(100, activation="relu")(topic_final)
    K_e= Dense(100, activation="relu")(topic_final)
    V_e= Dense(100, activation="relu")(topic_final)
    IA_topic=Lambda(attentionScores)([Q_e,K_e,V_e])

    IRAScores=Lambda(attentionScoresIRA1)([Q_t,K_t,V_t,Q_e,K_e,V_e])
    
    final_input=Concatenate()([IA_text,IA_topic,IRAScores])
    s_output=Dense(100, activation="relu", name="shared_layer")(final_input)
    
    stance_shared_output=Dense(2, activation="softmax", name="task_stance_shared")(s_output)
    senti_shared_output=Dense(3, activation="softmax", name="task_senti_shared")(s_output)

    model=Model([input1,input2],[stance_shared_output,senti_shared_output])

    #### K fold data ############
    test_sequence,train_sequence=total_sequence[test_index],total_sequence[train_index]
    test_sequence_topic,train_sequence_topic=total_sequence_topic[test_index],total_sequence_topic[train_index] 
    test_stance,train_stance=total_labels_stance[test_index],total_labels_stance[train_index]
    test_senti,train_senti=total_labels_senti[test_index],total_labels_senti[train_index]
    test_enc = np.argmax(test_stance, axis=1)
    train_enc = np.argmax(train_stance, axis=1)
    train_enc_senti = np.argmax(train_senti, axis=1)
    print("len of train",np.unique(train_enc,return_counts=True),len(train_stance))
    print("len of test",np.unique(test_enc,return_counts=True),len(test_stance))
    
    # oversample
    train_sequence,train_sequence_topic,train_enc,train_enc_senti=create_resample(train_sequence,train_sequence_topic,train_enc,train_enc_senti)
    train_sequence=np.array(train_sequence)
    train_sequence_topic=np.array(train_sequence_topic)
    train_stance=to_categorical(train_enc)
    train_senti=to_categorical(train_enc_senti)

    model.compile(optimizer=Adam(0.0001),loss={'task_stance_shared':'binary_crossentropy','task_senti_shared':'categorical_crossentropy'}, loss_weights={'task_senti_shared':0.5,'task_stance_shared':1.0}, metrics=['accuracy'])    
    print(model.summary())

    model.fit([train_sequence,train_sequence_topic],[train_stance,train_senti], shuffle=True,validation_split=0.2,epochs=20,verbose=2)
    predicted = model.predict([test_sequence,test_sequence_topic])

    test_enc = np.argmax(test_stance, axis=1)
    stance_pred_shared=predicted[0]
    result_=stance_pred_shared
    p_1 = np.argmax(result_, axis=1)
    test_accuracy=accuracy_score(test_enc, p_1)
    list_acc_stance.append(test_accuracy)
    print("test accuracy::::",test_accuracy)
    target_names = ['believer','deny']
    class_rep=classification_report(test_enc, p_1)
    print("specific confusion matrix",confusion_matrix(test_enc, p_1))
    print(class_rep)
    class_rep=classification_report(test_enc, p_1, target_names=target_names,output_dict=True)
    macro_avg=class_rep['macro avg']['f1-score']
    print("macro f1 score",macro_avg)
    list_f1_stance.append(macro_avg)

    ########### sentiment
    test_enc_senti = np.argmax(test_senti, axis=1)

    sent_pred_shared=predicted[1]
    result_=sent_pred_shared
    p_1 = np.argmax(result_, axis=1)
    test_accuracy=accuracy_score(test_enc_senti, p_1)
    list_acc_senti.append(test_accuracy)
    print("test accuracy::::",test_accuracy)
    target_names = ['negative', 'neutral', 'positive']
    class_rep=classification_report(test_enc_senti, p_1)
    print("specific confusion matrix",confusion_matrix(test_enc_senti, p_1))
    print(class_rep)
    class_rep=classification_report(test_enc_senti, p_1, target_names=target_names,output_dict=True)
    macro_avg=class_rep['macro avg']['f1-score']
    print("macro f1 score",macro_avg)
    list_f1_senti.append(macro_avg)

 
############# stance 

print("ACCURACY :::::::::::: #############")
print("act  ::: ",list_acc_stance)
print("Mean, STD DEV", statistics.mean(list_acc_stance),statistics.stdev(list_acc_stance))

print("F1  $$$$$$$$$$$$$$$$$ ::::::::::::")
print("Specific F1 ::: ",list_f1_stance)
print("MTL Mean, STD DEV", statistics.mean(list_f1_stance),statistics.stdev(list_f1_stance))


############# sentiment 

print("ACCURACY :::::::::::: #############")
print("act  ::: ",list_acc_senti)
print("Mean, STD DEV", statistics.mean(list_acc_senti),statistics.stdev(list_acc_senti))

print("F1  $$$$$$$$$$$$$$$$$ ::::::::::::")
print("Specific F1 ::: ",list_f1_senti)
print("MTL Mean, STD DEV", statistics.mean(list_f1_senti),statistics.stdev(list_f1_senti))

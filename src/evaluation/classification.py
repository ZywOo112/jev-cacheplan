"""Three-class metrics, with zero precision/recall denominators defined as zero."""
import numpy as np
def classification(gold,predicted,labels):
    if len(gold)!=len(predicted) or not gold:raise ValueError('Unaligned or empty labels')
    lookup={label:i for i,label in enumerate(labels)}
    matrix=np.zeros((len(labels),len(labels)),dtype=int)
    for truth,prediction in zip(gold,predicted):matrix[lookup[truth],lookup[prediction]]+=1
    support=matrix.sum(axis=1);predicted_counts=matrix.sum(axis=0);tp=np.diag(matrix).astype(float)
    precision=np.divide(tp,predicted_counts,out=np.zeros_like(tp),where=predicted_counts>0)
    recall=np.divide(tp,support,out=np.zeros_like(tp),where=support>0)
    f1=np.divide(2*precision*recall,precision+recall,out=np.zeros_like(tp),where=precision+recall>0)
    return {'n':len(gold),'accuracy':float(tp.sum()/matrix.sum()),'macro_f1':float(f1.mean()),
            'weighted_f1':float(np.dot(f1,support)/support.sum()),'confusion_matrix':matrix.tolist(),
            'labels':list(labels),'per_class':{label:{'precision':float(precision[i]),'recall':float(recall[i]),
            'f1':float(f1[i]),'support':int(support[i])} for i,label in enumerate(labels)}}

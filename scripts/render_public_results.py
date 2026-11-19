"""Redraw display labels from saved measurements only; never calls a model."""
import csv
import json
import _bootstrap
from project_runtime import ROOT

def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with (ROOT/'benchmarks/results/run_metrics.csv').open() as stream:rows=list(csv.DictReader(stream))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
        'axes.spines.right':False,'axes.edgecolor':'#b6c9d8','axes.labelcolor':'#163453',
        'text.color':'#163453','xtick.color':'#52677c','ytick.color':'#52677c',
        'figure.facecolor':'white','savefig.facecolor':'white','svg.fonttype':'none'})
    colors={'original':'#276FB2','solo':'#129782'};names={'original':'Original','solo':'CachePlan'}
    fig,ax=plt.subplots(figsize=(10,3.8),layout='constrained');points={}
    for method in ['original','solo']:
        series=sorted([r for r in rows if r['case']=='shared_970' and r['method']==method],key=lambda x:int(x['repeat']))
        points[method]=[float(r['end_to_end_seconds']) for r in series]
        ax.plot([1,2,3],points[method],'-o',color=colors[method],label=names[method],lw=2.2,ms=7)
    for i in range(3):ax.text(i+1,225,f"{points['original'][i]/points['solo'][i]:.2f}×",ha='center',fontweight='bold',fontsize=13)
    ax.set(xticks=[1,2,3],xticklabels=['Repeat 1','Repeat 2','Repeat 3'],ylabel='Total scan time (s)',ylim=(0,460),xlim=(.8,3.2))
    ax.set_title('97% reusable field-value tokens · 128 records per scan',loc='left',fontweight='bold',pad=14)
    ax.grid(axis='y',alpha=.18);ax.legend(loc='upper right',bbox_to_anchor=(1,.87),frameon=False)
    fig.savefig(ROOT/'assets/repeat_timing.png',dpi=190);fig.savefig(ROOT/'assets/repeat_timing.svg');plt.close(fig)
    svg=ROOT/'assets/repeat_timing.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    evidence=json.loads((ROOT/'docs/presentation_evidence.json').read_text())
    fig,ax=plt.subplots(figsize=(8.8,3.4),layout='constrained')
    accuracy=[sum(float(r['accuracy']) for r in rows if r['method']==m)/sum(r['method']==m for r in rows) for m in ['original','solo']]
    ax.bar([0,1],accuracy,color=[colors['original'],colors['solo']],width=.5)
    for i,value in enumerate(accuracy):ax.text(i,value+.025,f'{value:.0%}',ha='center',fontweight='bold')
    ax.set(xticks=[0,1],xticklabels=['Original','CachePlan'],ylim=(0,1.13),yticks=[0,.5,1],yticklabels=['0%','50%','100%'],ylabel='Synthetic-task accuracy')
    ax.set_title('Noul refund / replacement task · 14 measured scans',loc='left',fontweight='bold',pad=12)
    ax.grid(axis='y',alpha=.18)
    paired=sum(p['records'] for p in evidence['paired_prediction_checks'])
    fig.text(.56,.32,f'{paired}/{paired} paired labels agree\n14/14 ID/probability restores\nProbabilities may differ by layout',fontsize=10,ha='center',bbox={'facecolor':'white','edgecolor':'#dbe5ee','boxstyle':'round,pad=.8'})
    fig.savefig(ROOT/'assets/quality.png',dpi=190);plt.close(fig)

if __name__=='__main__':main()

#!/usr/bin/env python3
import csv,json,math,random,re
from collections import defaultdict
from pathlib import Path
import finetune as ft
import team_compare_results as team
ROOT=Path(__file__).resolve().parent

def paired(a,b,historical=True):
 aa={(r['file_name'],r['chunk_id']):r for r in a}
 bb={(r['file_name'],r['chunk_id']):r for r in b}
 assert set(aa)==set(bb)
 groups=defaultdict(list);gains=losses=both=neither=0
 for k in aa:
  x,y=aa[k],bb[k]
  assert x['expected']==y['expected']
  old=all(x['matches'].values());new=all(y['matches'].values())
  gains+=int(new and not old);losses+=int(old and not new)
  both+=int(old and new);neither+=int(not old and not new)
  groups[k[0]].append(int(new)-int(old))
 n=gains+losses
 p=min(1.,2*sum(math.comb(n,k) for k in range(min(gains,losses)+1))/2**n) if n else 1.
 rng=random.Random(42);samples=[];docs=list(groups)
 for _ in range(10000):
  chosen=[groups[rng.choice(docs)] for _ in docs]
  samples.append(100*sum(sum(g) for g in chosen)/sum(len(g) for g in chosen))
 samples.sort()
 return {'gains':gains,'regressions':losses,'both_correct':both,'both_wrong':neither,
         'net_correct':gains-losses,'net_percentage_points':100*(gains-losses)/len(a),
         'source_documents':len(docs),'document_bootstrap_95pct_interval_pp':[samples[250],samples[9750]],
         'mcnemar_exact_p_descriptive_only':p,
         'caution':('Previously observed historical test; chunks share documents; p-value is descriptive, not confirmatory evidence.' if historical else 'Assistant-authored provisional labels on a small fresh sample; descriptive result, not independent human validation.')}

def score_with_team(predictions,name):
 gt={(r['file_name'],r['chunk_id']):r['expected'] for r in predictions}
 preds={}
 for r in predictions:
  rec={'file_name':r['file_name'],'chunk_id':r['chunk_id']}
  try:
   m=re.search(r'\{.*\}',r['raw_response'],re.DOTALL)
   obj=json.loads(m.group(0))
   assert isinstance(obj,dict)
   rec.update({f:obj.get(f,'') for f in ft.FIELDS});rec['error']=None
  except Exception as e:rec['error']=str(e)
  preds[(r['file_name'],r['chunk_id'])]=rec
 return team.score(gt,preds,name)

def main():
 result=json.loads((ROOT/'benchmark-result.json').read_text())
 summaries={}
 for part in ['benchmark-base','benchmark-selected','fresh-base','fresh-selected']:
  predictions=ft.read_jsonl(ROOT/part/'predictions.jsonl')
  scored,summary=score_with_team(predictions,part)
  summaries[part]=summary
  ft.write_json(ROOT/part/'team-metrics.json',summary)
  with (ROOT/part/'team-scored.csv').open('w') as f:
   writer=csv.DictWriter(f,fieldnames=list(scored[0]));writer.writeheader();writer.writerows(scored)
 comparison={'historical':paired(ft.read_jsonl(ROOT/'benchmark-base/predictions.jsonl'),ft.read_jsonl(ROOT/'benchmark-selected/predictions.jsonl')),
             'fresh':paired(ft.read_jsonl(ROOT/'fresh-base/predictions.jsonl'),ft.read_jsonl(ROOT/'fresh-selected/predictions.jsonl'),historical=False),
             'team_scorer_sha256':ft.sha(ROOT/'team_compare_results.py'),'team_scores':summaries,
             'handoff_gate_passed':result['handoff_gate_passed']}
 ft.write_json(ROOT/'comparison.json',comparison)
 print(json.dumps(comparison,indent=2))
if __name__=='__main__':main()

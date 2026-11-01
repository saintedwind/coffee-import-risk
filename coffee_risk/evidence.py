"""Private evidence manifest. Documents are never executed or inferred into verified inputs."""
from dataclasses import asdict
from datetime import date
import hashlib,json,math
from pathlib import Path

STATUSES=('documented','user_reported','public_listing','assumption','missing')
STAGES=('green','roasted')
ALLOWED_SUFFIXES={'.pdf','.png','.jpg','.jpeg','.xlsx','.csv','.txt'}

def store_document(folder,name,raw):
    if not raw or len(raw)>5_000_000: raise ValueError('Document must be between 1 byte and 5 MB')
    suffix=Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES: raise ValueError('Unsupported evidence type')
    digest=hashlib.sha256(raw).hexdigest();folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(digest+suffix)
    if not path.exists():
        with path.open('xb') as stream:stream.write(raw)
    return {'document_id':digest,'sha256':digest,'name':Path(name).name,'stored_file':path.name,'bytes':len(raw)}

def validate_manifest(manifest):
    if not isinstance(manifest,dict) or manifest.get('schema')!='coffee-evidence-1': raise ValueError('Invalid evidence schema')
    fields=manifest.get('fields',[]);documents=manifest.get('documents',[])
    if not isinstance(fields,list) or len(fields)>100 or not isinstance(documents,list) or len(documents)>50: raise ValueError('Manifest too large')
    ids={d['document_id'] for d in documents};seen=set()
    for row in fields:
        key=row.get('field')
        if key in seen or key not in asdict(__import__('coffee_risk.model',fromlist=['Deal']).Deal()): raise ValueError('Unknown or duplicate deal field')
        seen.add(key)
        if row.get('status') not in STATUSES:raise ValueError('Invalid evidence status')
        if row['status']!='missing':
            if not isinstance(row.get('value'),(float,int)) or not math.isfinite(row['value']):raise ValueError('Finite numeric value required')
            if row.get('unit') not in ('IRR','toman','USD/kg','kg','USD','fraction','months'):raise ValueError('Explicit supported unit required')
            expected=('IRR' if '_irr' in key else 'USD/kg' if '_usd_kg' in key else 'USD' if key=='freight_usd' else 'kg' if key=='quantity_kg' else 'months' if key=='months' else 'fraction')
            if row['unit'] not in (('IRR','toman') if expected=='IRR' else (expected,)):raise ValueError('Unit does not match deal field')
            if not row.get('source'):raise ValueError('Source required')
            if date.fromisoformat(row['observed_date'])>date.today():raise ValueError('Future evidence date')
        if row['status']=='documented' and row.get('document_id') not in ids:raise ValueError('Documented value needs a linked document')
    return manifest

def manifest_from_deal(deal,sources,documents=()):
    fields=[]
    for key,value in asdict(deal).items():
        source=sources.get(key,{})
        unit=('IRR' if '_irr' in key else 'USD/kg' if '_usd_kg' in key else 'USD' if key=='freight_usd' else 'kg' if key=='quantity_kg' else 'months' if key=='months' else 'fraction')
        fields.append({'field':key,'value':value,'unit':unit,'status':source.get('status','assumption'),
                      'source':source.get('source','Illustrative assumption; no supporting document'),
                      'observed_date':source.get('observed_date',date.today().isoformat()),'document_id':source.get('document_id')})
    return validate_manifest({'schema':'coffee-evidence-1','documents':list(documents),'fields':fields})

def apply_manifest(manifest):
    from .model import Deal
    from .money import to_irr
    validate_manifest(manifest);values={}
    for row in manifest['fields']:
        if row['status']=='missing':continue
        key=row['field'];value=row['value']
        if '_irr' in key:
            value=to_irr(value,row['unit'])
        elif row['unit']=='toman':raise ValueError('Toman only allowed for IRR-valued model fields')
        if key=='months':
            if int(value)!=value:raise ValueError('Months must be integral')
            value=int(value)
        values[key]=value
    deal=Deal(**values);deal.validate()
    missing=[key for key in asdict(Deal()) if key not in values]
    if missing: raise ValueError('Incomplete manifest: '+','.join(missing))
    return deal

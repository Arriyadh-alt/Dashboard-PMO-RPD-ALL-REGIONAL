"""In-browser adapter for the SAME analytics/reports. Not a security boundary or server.

Only encrypted local events are persisted by the JavaScript controller. No records,
passwords or decrypted event payloads are written to browser storage.
"""
import base64
import copy
from datetime import date, datetime, timezone
from urllib.parse import parse_qs,urlsplit

from .analytics import DEFAULT_RULES,area_key,build_analysis,period_bounds,prepare,quality,record_view,scoped_rows,target_ref
from .exports import TITLES,make_report,report_content


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class LocalEvents:
    """Append-only application history, not a tamper-proof/shared audit ledger."""
    def __init__(self,events=None):
        self.events=copy.deepcopy(events or [])
        if not isinstance(self.events,list) or len(self.events)>100000:
            raise ValueError('Local history invalid or too large')
        last=0
        for event in self.events:
            if not isinstance(event,dict) or not isinstance(event.get('id'),int) or event['id']<=last or not isinstance(event.get('payload'),dict) or not all(isinstance(event.get(key),str) for key in ['kind','ref','actor','at']):
                raise ValueError('Local history format invalid')
            last=event['id']

    def append(self,kind,ref,actor,payload):
        event_id=(self.events[-1]['id'] if self.events else 0)+1
        self.events.append(dict(id=event_id,kind=kind,ref=ref,actor=actor,at=now(),payload=copy.deepcopy(payload)))
        return event_id

    def history(self,kind=None,ref=None,limit=100,before=None):
        return [copy.deepcopy(row) for row in reversed(self.events) if (kind is None or row['kind']==kind) and (ref is None or row['ref']==ref) and (before is None or row['id']<before)][:limit]

    def latest(self,kind):
        return {row['ref']:copy.deepcopy(row['payload']) for row in self.events if row['kind']==kind}

    def append_if_current(self,kind,ref,actor,payload,expected):
        history=self.history(kind,ref,1)
        if (history[0]['id'] if history else 0)!=expected:
            raise ValueError('Mapping changed. Reload before editing again.')
        return self.append(kind,ref,actor,payload)


def integer(value,minimum,maximum):
    if isinstance(value,bool) or (isinstance(value,float) and not value.is_integer()):
        raise ValueError('Invalid integer')
    result=int(value)
    if not minimum<=result<=maximum:
        raise ValueError('Value outside allowed range')
    return result


def text(body,key,maximum,required=False,default=''):
    value=body.get(key,default)
    if not isinstance(value,str) or len(value)>maximum or (required and not value.strip()):
        raise ValueError('Invalid field: '+key)
    return value


class BrowserAPI:
    def __init__(self,source,role,actor,info,events=None):
        self.data=source
        self.prepared=prepare(source)
        self.role=role
        self.actor=actor
        self.info=info
        self.store=LocalEvents(events)

    def scope(self,raw):
        source=self.data
        filters={key:integer(raw.get(key,default),low,high) for key,default,low,high in [('m0',0,0,len(source['months'])-1),('m1',len(source['months'])-1,0,len(source['months'])-1),('ab',-1,-1,len(source['abs'])-1),('kel',-1,-1,len(source['kels'])-1)]}
        filters.update({key:text(raw,key,maximum) for key,maximum in [('reg',100),('coordinator',150),('start',10),('end',10)]})
        statuses=raw.get('statuses',[])
        if not isinstance(statuses,list) or len(statuses)>30 or any(not isinstance(value,str) for value in statuses):
            raise ValueError('Invalid status filter')
        filters['statuses']=statuses
        period_bounds(source,filters)
        return filters

    def bootstrap(self):
        source=self.data
        safe={key:source[key] for key in ('months','abs','reg','kels','svs','st','kl','A','S','E','P','W','dic')}
        safe['meta']={key:source['meta'].get(key,[] if key=='korlaps' else {} if key=='sync' else 0) for key in ('tmin','tmax','rows','uniq','sync','korlaps','rt_bad')}
        if self.role!='owner':
            safe['svs']=[f'Surveyor {index+1}' for index in range(len(source['svs']))]
        mapping=self.store.history('mapping','all',1)
        overrides=mapping[0]['payload'] if mapping else {}
        pairs={(row['ab'],row['kel']) for row in self.prepared['rows'] if row['valid_location']}
        pairs.update((row[0],row[1]) for row in [*source['P'],*source['W']] if len(row)>=2 and type(row[0]) is int and type(row[1]) is int and 0<=row[0]<len(source['abs']) and 0<=row[1]<len(source['kels']))
        return dict(data=safe,role=self.role,csrf='',overrides={str(index):overrides[name] for index,name in enumerate(source['svs']) if name in overrides},mapping_version=mapping[0]['id'] if mapping else 0,geography=sorted(pairs),area_keys=[area_key(source,index) for index in range(len(source['abs']))],data_owner=self.info.get('owner',''),source=self.info,capabilities=dict(customer_detail=self.role=='owner',attendance=False,geographic_boundaries=False,historical_snapshots=False,browser_only=True))

    def request(self,path,method='GET',body=None):
        body=body or {}
        url=urlsplit(path)
        query=parse_qs(url.query,keep_blank_values=True)
        raw={key:values[-1] for key,values in query.items()}
        raw['statuses']=query.get('status',[])
        route=url.path
        expected={'/api/records/search':'POST','/api/admin/mappings':'PUT','/api/admin/rules':'PUT','/api/admin/targets':'POST','/api/admin/area-context':'POST'}
        allowed=('GET','POST') if route.startswith('/api/followups/') else (expected.get(route,'GET'),)
        if method not in allowed: raise ValueError('Invalid local request method')
        if route=='/api/bootstrap': return self.bootstrap()
        if route=='/api/analysis': return build_analysis(self.data,self.prepared,self.scope(raw),self.store,self.role)
        if route=='/api/quality': return {**quality(self.data,self.prepared),'source':self.info}
        if route.startswith('/api/reports/'):
            kind,extension=route.rsplit('/',1)[-1].rsplit('.',1)
            if kind not in TITLES or extension not in ('csv','xlsx','pdf'): raise ValueError('Unknown report')
            filters=self.scope(raw)
            analysis=build_analysis(self.data,self.prepared,filters,self.store,self.role)
            info={**self.info,'imported_at':None}
            if extension=='pdf':
                headers,rows,metadata=report_content(kind,extension,analysis,self.data,self.prepared,filters,self.store,self.role,info)
                return {'pdf_model':dict(headers=headers,rows=rows,metadata=metadata)}
            content,media=make_report(kind,extension,analysis,self.data,self.prepared,filters,self.store,self.role,info)
            return {'binary':base64.b64encode(content).decode(),'media_type':media}
        if self.role!='owner': raise ValueError('View unavailable in this presentation role. Browser roles are not server authorization.')
        source,prepared,store=self.data,self.prepared,self.store
        if route=='/api/legacy-report.pdf':
            if not source.get('pdf'): raise ValueError('Legacy PDF unavailable')
            return {'binary':source['pdf'],'media_type':'application/pdf'}
        if route=='/api/records/search':
            filters=self.scope(body.get('scope',{}));overrides=store.latest('mapping').get('all',{});actions=store.latest('followup')
            offset=integer(body.get('offset',0),0,10**9);limit=integer(body.get('limit',50),1,100)
            selected=[];total=0
            for row in scoped_rows(source,prepared,filters,overrides):
                if body.get('pam') and not row['pam'].startswith(str(body['pam']).strip().lstrip('0')): continue
                if body.get('kelurahan') and body['kelurahan'].casefold() not in source['kels'][row['kel']].casefold(): continue
                if body.get('surveyor') and body['surveyor'].casefold() not in source['svs'][row['sv']].casefold(): continue
                if any(body.get(field) and row[key]!=body[field] for field,key in [('canvassing','c1'),('installation','kf'),('potential','pr')]): continue
                if body.get('outstanding_only') and not (row['interest'] and not row['installed'] and not row['cancelled']): continue
                if offset<=total<offset+limit: selected.append(record_view(source,prepared,row,overrides,actions.get(row['ref'])))
                total+=1
            return dict(rows=selected,total=total,offset=offset,limit=limit)
        if route.startswith('/api/followups/'):
            ref=route.rsplit('/',1)[-1]
            if not any(row['valid'] and row['ref']==ref for row in prepared['rows']): raise ValueError('Unknown case in current source')
            if method=='GET':
                limit=integer(raw.get('limit',100),1,1000);before=integer(raw['before'],1,10**9) if raw.get('before') else None
                events=store.history('followup',ref,limit,before)
                return dict(events=events,next_before=events[-1]['id'] if len(events)==limit else None)
            payload={key:text(body,key,maximum,key in ('pic','status','action')) for key,maximum in [('pic',150),('status',100),('action',2000),('resolution_notes',2000),('pause_reason',500)]}
            if payload['status'] not in source['dic']['kf'] and payload['status']!='Tidak tercatat': raise ValueError('Use an original operational status')
            for key in ['target_date','case_started']:
                payload[key]=date.fromisoformat(body[key]).isoformat() if body.get(key) else None
            payload['pause_days']=integer(body.get('pause_days',0),0,36500)
            if payload['case_started'] and not 0<=payload['pause_days']<=(date.today()-date.fromisoformat(payload['case_started'])).days: raise ValueError('Invalid verified start/pause duration')
            if payload['pause_days'] and (not payload['case_started'] or not payload['pause_reason'].strip()): raise ValueError('Verified pause requires start and reason')
            payload['updated_at']=now()
            return dict(ok=True,event_id=store.append('followup',ref,self.actor,payload))
        if route=='/api/admin/mappings':
            values=body.get('values',{});active=set(source['svs'])
            converted={name:value for name,value in store.latest('mapping').get('all',{}).items() if name not in active}
            allowed=[*source['meta'].get('korlaps',[]),'PENGAWAS','BELUM TERDAFTAR','AKUN GENERIK']
            if not isinstance(values,dict) or len(values)>len(source['svs']): raise ValueError('Invalid mapping')
            for index,value in values.items():
                index=integer(index,0,len(source['svs'])-1)
                if not isinstance(value,dict) or set(value)-{'kl','st'} or ('kl' in value and value['kl'] not in allowed) or ('st' in value and (type(value['st']) is not int or value['st'] not in (0,1,2))): raise ValueError('Invalid coordinator/status')
                converted[source['svs'][index]]=value
            return dict(ok=True,version=store.append_if_current('mapping','all',self.actor,converted,integer(body.get('version',0),0,10**9)))
        if route=='/api/admin/targets':
            month=text(body,'month',7,True);region=text(body,'region',100);area=integer(body.get('area',-1),-1,len(source['abs'])-1)
            if month not in source['months'] or (region and region not in source['reg']) or (area>=0 and source['reg'][area]!=region): raise ValueError('Invalid target scope')
            payload=dict(month=month,region=region,area=area,target=integer(body.get('target'),1,10000000),evidence=text(body,'evidence',1000,True),area_name=source['abs'][area] if area>=0 else '')
            store.append('target',target_ref(month,region,area,source),self.actor,payload)
            return {'ok':True}
        if route=='/api/admin/rules':
            payload={'minimum_sample':integer(body.get('minimum_sample',20),1,100000)}
            for key,default in [('high_backlog_rate',.3),('cooling_interest_rate',.1)]:
                value=float(body.get(key,default))
                if not (0<value<=1 if key=='high_backlog_rate' else 0<=value<=1): raise ValueError('Invalid priority rule')
                payload[key]=value
            store.append('rules','all',self.actor,payload)
            return {'ok':True}
        if route=='/api/admin/area-context':
            area=integer(body.get('area'),0,len(source['abs'])-1)
            if body.get('supply') not in ('unknown','ready','constrained') or body.get('readiness') not in ('unknown','ready','blocked'): raise ValueError('Invalid readiness state')
            payload=dict(area=area,supply=body['supply'],readiness=body['readiness'],evidence=text(body,'evidence',1000,True),area_name=source['abs'][area],region=source['reg'][area])
            store.append('area_context',area_key(source,area),self.actor,payload)
            return {'ok':True}
        if route=='/api/admin/audit':
            limit=integer(raw.get('limit',100),1,1000);before=integer(raw['before'],1,10**9) if raw.get('before') else None
            events=store.history(limit=limit,before=before);contexts=store.latest('area_context')
            return dict(events=events,next_before=events[-1]['id'] if len(events)==limit else None,targets=store.latest('target'),area_context={str(index):contexts[area_key(source,index)] for index in range(len(source['abs'])) if area_key(source,index) in contexts},rules={**DEFAULT_RULES,**store.latest('rules').get('all',{})})
        raise ValueError('Unsupported local operation')

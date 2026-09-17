#!/usr/bin/env python3
"""人生副本口播稿质地体检（人生副本实录.md 第十四节门槛）。用法: python3 scripts/check_fuben_texture.py 作品/xx/正文.md"""
import re,sys
SENS=r'味|臭|酸|腥|油腻|粘|冰冷|刺|疼|痛|发白|发黄|锈|霉|汗|烫|冻|麻|涩|呛'
BRAND=r'拼夕夕|拼多多|红双喜|本田|迈巴赫|星巴克|沙县|五菱|帕萨特|支付宝|花呗|快手|抖音|美团|饿了么|玉溪|耐克|安卓|高德|白沙|华为|小米|苹果|iPhone|微信|蜜雪|瑞幸|优衣库|海澜之家|安踏|大众|比亚迪|哈啰|滴滴|boss直聘|BOSS|58同城|智联|钉钉|红牛|老坛|康师傅|统一|中华|利群|南京|黄鹤楼|雅迪|爱玛|台铃'
MEME=r'哈基米|验牌|急哭|尊嘟假嘟|活人微死|毛囊报警|邪修|老叟戏顽童|允许一切发生|我去不早说|栓Q|破防|绝绝子|yyds|city不city|尊嘟|班味|丝瓜汤'
def check(path):
    t=open(path,encoding='utf-8').read()
    lines=[l for l in t.split('\n') if l.strip() and not l.startswith('#')]
    txt=''.join(lines); n=len(txt)
    sens=len(re.findall(SENS,txt))/n*1000
    price=len(re.findall(r'\d+(?:\.\d+)?\s*(?:块|元|万|毛)',txt))
    brand=len(set(re.findall(BRAND,txt)))
    dlg=sum(1 for l in lines if re.search(r'(你说|他说|她说|说 |问 |喊 |：)',l))/len(lines)*100
    meme=re.findall(MEME,txt)
    head=''.join(lines[:3]); head_ok=bool(re.search(SENS+r'|块|元|℃|度',head))
    rows=[('字数',n,n>=2800,'≥2800'),('感官/千字',round(sens,1),sens>=6,'≥6'),('价格数',price,price>=12,'≥12'),
          ('品牌数',brand,brand>=4,'≥4'),('对话行%',round(dlg,1),dlg<=3,'≤3'),('热梗',len(meme),len(meme)==0,'=0'),('开篇3行落到皮肤',head_ok,head_ok,'True')]
    bad=0
    for k,v,ok,th in rows:
        print(f"{'OK ' if ok else 'BAD'} {k:10} {v}  (门槛 {th})"); bad+= not ok
    print('RESULT:', 'PASS' if not bad else f'FAIL {bad}项'); return bad
def check_comedy(path):
    t=open(path,encoding='utf-8').read()
    lines=[l for l in t.split('\n') if l.strip() and not l.startswith('#')]
    txt=''.join(lines); n=len(txt); meme=re.findall(MEME,txt)
    # 笑点节点近似：含数字/制度词/误会词/反差词的行
    nodes=sum(1 for l in lines if re.search(r'\d|规定|表格|Excel|公告|举报|以为|其实|居然|一模一样|默认|流程|条例|评分|投票|截图|收到',l))
    rows=[('字数',n,2100<=n<=3900,'2100–3900'),('制度/数字行占比(advisory)',round(nodes/n*1000,1),True,'参考: 32=3.3 39=11 29=7.6'),('热梗',len(meme),len(meme)==0,'=0')]
    bad=0
    for k,v,ok,th in rows:
        print(f"{'OK ' if ok else 'BAD'} {k:10} {v}  (门槛 {th})"); bad+= not ok
    print('RESULT:', 'PASS' if not bad else f'FAIL {bad}项'); return bad
if __name__=='__main__':
    args=[a for a in sys.argv[1:] if a!='--mode' and a!='comedy']
    fn=check_comedy if 'comedy' in sys.argv else check
    sys.exit(min(1,sum(fn(p) for p in args)))

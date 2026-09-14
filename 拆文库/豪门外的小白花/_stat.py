import re, json

p = 'C:/Users/29471/Desktop/dream/oh-story-claudecode/拆文库/豪门外的小白花/原文/豪门外的小白花.txt'
t = open(p, encoding='utf-8').read()
sep = '━' * 63
parts = t.split(sep)
body = parts[-1].split(sep)[0]
body = body.replace('（全文完）备案号:YXX1BBRzXNDHMEE84LhBGGD', '')
print('body chars', len(body))

pos = []
for m in re.finditer(r'(?m)^(\d+)\.([?？]?)\s*$', body):
    pos.append((int(m.group(1)), m.start(), m.group(2)))
for n, s, q in pos:
    print(n, s, q)

dia = re.findall(r'「(.*?)」', body, re.S)
dc = sum(len(d) for d in dia)
print('dialogue chars', dc, 'ratio', round(dc / len(body) * 100, 1), 'count', len(dia))

# section lengths based on markers
bounds = [(n, s) for n, s, q in pos]
bounds.append((99, len(body)))
print('--- section char length ---')
for i in range(len(bounds) - 1):
    n1, s1 = bounds[i]
    n2, s2 = bounds[i + 1]
    seg = body[s1:s2]
    d = sum(len(x) for x in re.findall(r'「(.*?)」', seg, re.S))
    print(n1, len(seg), 'dialogue%', round(d / max(len(seg), 1) * 100, 1))
print('pre-1 length', bounds[0][1])

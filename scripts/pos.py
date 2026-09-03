#!/usr/bin/env python3
"""打印短语在分篇正文中的字符偏移（不含换行），用于拆文报告里的字数定位。用法：pos.py 文件 短语1 短语2 ..."""
import sys
f=sys.argv[1]
t=open(f,encoding='utf-8').read().split('\n',4)[4].replace('\n','')
print(f"总字数 {len(t)}")
for p in sys.argv[2:]:
    i=t.find(p)
    print(f"{i:>5} ({i*100//len(t) if i>=0 else -1:>3}%)  {p}")

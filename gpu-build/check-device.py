# 置換前後の公開シンボルを比較する。
import subprocess,json
old='/opt/rocm/lib/migraphx/lib/libmigraphx_device.so.2015000'
new='/work/device-build/libmigraphx_device.so.2015000.0.70200'
def symbols(p):
 out=subprocess.check_output(['/usr/bin/nm','-D','--defined-only',p],text=True)
 return {line.split()[-1] for line in out.splitlines() if len(line.split())>=3 and line.split()[-2]=='T' and line.split()[-1].startswith('_ZN8migraphx')}
a=symbols(old);b=symbols(new)
print(json.dumps({'original_symbols':len(a),'rebuilt_symbols':len(b),'missing':sorted(a-b)}))
assert not (a-b)

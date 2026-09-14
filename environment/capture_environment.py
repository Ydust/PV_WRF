"""Record Python and package versions from the current environment."""
from pathlib import Path
import sys,json,importlib.metadata as md
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
R=Path(__file__).resolve().parent
roots=['numpy','pandas','scipy','numba','llvmlite','matplotlib','pillow','cartopy','shapely','pyproj','pyshp','ipykernel','nbformat','nbclient']
seen={};todo=list(roots)
while todo:
    name=canonicalize_name(todo.pop())
    if name in seen:continue
    d=md.distribution(name);seen[name]=d.version
    for spec in d.requires or []:
        req=Requirement(spec)
        if req.marker is None or req.marker.evaluate({'extra':''}):todo.append(req.name)

(R/'requirements-lock.txt').write_text('\n'.join(f'{k}=={v}' for k,v in sorted(seen.items()))+'\n',encoding='utf8')
(R/'observed_environment.json').write_text(json.dumps({'python_version':sys.version.split()[0],'platform':sys.platform,'direct_dependencies':roots,'packages':seen},indent=2),encoding='utf8')
print(json.dumps(seen,indent=2))

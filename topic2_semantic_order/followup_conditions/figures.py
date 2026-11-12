"""Standalone SVG figures, rendered with the original study's plotting helper."""
from statistics import mean
import sys

from common import *
from explore import rows

sys.path.insert(0,str(T2/"analysis"))
from make_figures import grouped


def main():
    target=HERE/"figures"
    target.mkdir(exist_ok=True)
    tv=rows("window_tv")
    for level in ("coarse","fine"):
        modes=("record","input","loss","lr","lr_loss")
        values=[[100*mean(float(r[m]) for r in tv if r["arm"]==a and r["level"]==level)
                 for m in modes] for a in "AB"]
        fig=grouped(f"{level.title()} exposure by weight (mean across five orders)",
                    ["Record","Input tokens","Loss tokens","LR","LR × loss"],*values,
                    max(*values[0],*values[1])*1.25,"window TV (%)")
        (target/f"exposure_{level}.svg").write_text(fig,encoding="utf-8")
    r=rows("evaluation_per_run")
    for key,title in (("T1","T1 fare accuracy"),("worst","Worst eligible fine group accuracy")):
        values=[[100*float(next(x for x in r if x["dataset"]=="CT10K" and x["arm"]==a and int(x["seed"])==s)[key])
                 for s in SEEDS] for a in "AB"]
        (target/f"ct10k_{key}.svg").write_text(grouped(f"CT10K: {title} by seed",
                  [str(s) for s in SEEDS],*values,100,"accuracy (%)"),encoding="utf-8")


if __name__=="__main__":
    main()

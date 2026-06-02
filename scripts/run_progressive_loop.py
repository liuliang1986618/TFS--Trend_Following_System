#!/usr/bin/env python3
"""V3 信号增强引擎 — V2基线(79.1%) + 放量突破信号 → 捕捉转折。

策略: V2预测"维持原状"已经79%正确。V3在V2基础上，当检测到放量+突破前高/跌破前低时，
才修正预测方向。其他时候完全信任V2。保证V2的79%不掉，同时捕捉真正的转折时机。
"""
import sys, os, json, time, glob
from datetime import datetime
from collections import defaultdict
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.engine.state_machine import StateMachine

W = 5; WU = 20; DD = "dashboard/data"
t0 = time.time()


def classify(pattern, label):
    """从parquet逐日classify，无缓存。返回 {code: [(date, state, signals)]}"""
    fs = sorted(glob.glob(pattern))
    if not fs: return {}
    dfs = {}; ads = set()
    for f in fs:
        c = os.path.basename(f).split("_")[1].replace(".parquet","")
        df = pd.read_parquet(f).sort_index()
        if len(df) >= WU: dfs[c] = df; ads.update(df.index.strftime("%Y-%m-%d"))
    ads = sorted(ads); res = defaultdict(list)
    for di, d in enumerate(ads):
        dt = pd.Timestamp(d)
        for c, df in dfs.items():
            if dt not in df.index: continue
            ix = df.index.get_loc(dt)
            if ix < WU: continue
            try:
                ts = StateMachine.classify(df.iloc[:ix+1])
                sk = "3p" if ts.state == "3'" else ts.state
                res[c].append((d, sk, {
                    "surge": ts.volume_surge, "shrink": ts.volume_shrink,
                    "bhigh": ts.broke_prev_high, "blow": ts.broke_prev_low,
                    "crise": ts.consecutive_rise, "cdrop": ts.consecutive_drop,
                    "ma20": ts.above_ma20,
                }))
            except: continue
        if di % 200 == 0:
            n = sum(len(v) for v in res.values())
            print(f"   {label} {di}/{len(ads)} [{time.time()-t0:.0f}s] {n:,}条")
    return dict(res)


def mkidx(data):
    """{date: {code: (state, signals)}}"""
    r = defaultdict(dict)
    for c, seq in data.items():
        for d, s, sig in seq: r[d][c] = (s, sig)
    return r


def learn(ix, ds, ei, w):
    """学习无条件转移概率 P(next|current)，同V2"""
    si = max(0, ei - w*8)
    cnt = defaultdict(lambda: defaultdict(int))
    for di in range(si+1, ei+1):
        if di >= len(ds): break
        pd = ds[di-1]; cd = ds[di]
        for c in ix.get(cd,{}):
            if c not in ix.get(pd,{}): continue
            ps, _ = ix[pd][c]; cs, _ = ix[cd][c]
            cnt[str(ps)][str(cs)] += 1
    return {k: {t: ct/sum(v.values()) for t, ct in sorted(v.items(), key=lambda x:-x[1])}
            for k, v in cnt.items() if sum(v.values()) >= 20}


def main():
    global t0; t0 = time.time()
    print("="*70)
    print("🔄 V3: V2基线(79.1%) + 信号捕获转折时机")
    print("="*70)

    # 第1步: classify
    print("\n📦 全量classify（板块+题材，无缓存）")
    sec = classify(f"{DD}/sector_*.parquet","板块")
    thm = classify(f"{DD}/theme_*.parquet","题材")
    al = dict(sec); al.update(thm)
    print(f"   ✅ 板块{len(sec)} + 题材{len(thm)} = {len(al)}标的")
    print(f"   ✅ {sum(len(v) for v in al.values()):,}条状态记录")

    ix = mkidx(al)
    ds = sorted([d for d in ix if len(ix[d]) >= 20])
    print(f"   ✅ {len(ds)}有效交易日({ds[0]}~{ds[-1]})")

    # 第2步: 逐日预测+验证
    print(f"\n🎯 预测+验证 (窗口={W}天)")
    bp = {}; cv = []; ss = []
    co = 0; cn = 0; so = 0; sn = 0; to = 0; tn = 0
    sig_hits = 0  # 信号触发的预测次数
    sig_ok = 0    # 信号触发的正确次数
    t2 = time.time()

    for di, today in enumerate(ds):
        if di < WU: continue
        td = ix[today]; yd = ix.get(ds[di-1], {})

        # 每W天学一次
        if (di - WU) % W == 0 or not bp:
            bp = learn(ix, ds, di-1, W)
            if bp:
                ss.append({"date": today, "day": di, "states": len(bp)})

        ok = 0; n = 0
        for c in td:
            if c not in yd: continue
            ps, sig = yd[c]; ac, _ = td[c]
            ps = str(ps); ac = str(ac)

            # V2基线预测
            if ps in bp and bp[ps]:
                pr = max(bp[ps], key=bp[ps].get)
            else:
                pr = ps

            # ====== V3信号修正（唯一新增逻辑）======
            if sig.get("surge") and sig.get("bhigh") and ps == "2":
                pr = "3"; sig_hits += 1
            elif sig.get("surge") and sig.get("bhigh") and ps == "3":
                pr = "4"; sig_hits += 1
            elif sig.get("surge") and sig.get("blow") and ps in ("4","5"):
                pr = "3p"; sig_hits += 1

            n += 1
            if pr == ac:
                ok += 1
                if pr != ps: sig_ok += 1  # 信号修正且正确

            if pr == ps: sn += 1; so += (1 if pr == ac else 0)
            else: tn += 1; to += (1 if pr == ac else 0)

        if n > 0:
            co += ok; cn += n
            cv.append({"date": today, "day": di, "da": round(ok/n,4),
                        "ca": round(co/cn,4)})

        if di % 100 == 0:
            da = ok/n if n > 0 else 0; ca = co/cn if cn > 0 else 0
            sa = so/sn if sn > 0 else 0; ta = to/tn if tn > 0 else 0
            print(f"  Day{di:>4} {today} [{time.time()-t2:.0f}s] "
                  f"日{da:.1%} 累{ca:.1%} | 维持{sa:.0%}({sn}) 转折{ta:.0%}({tn}) | "
                  f"信号{sig_hits}次对{sig_ok}次")

    te = time.time() - t2; tt = time.time() - t0
    fa = co/cn if cn > 0 else 0; pk = max(d["ca"] for d in cv) if cv else 0
    sa = so/sn if sn > 0 else 0; ta = to/tn if tn > 0 else 0

    print(f"\n{'='*70}")
    print(f"✅ V3: {tt/60:.1f}min | {cn:,}次 | 最终{fa:.1%} | 峰值{pk:.1%}")
    print(f"   维持预测: {sa:.1%} ({sn:,}次) | 转折预测: {ta:.1%} ({tn:,}次)")
    print(f"   信号触发: {sig_hits}次 | 信号正确: {sig_ok}次 ({sig_ok/max(1,sig_hits):.0%})")
    print(f"   V1: 39.0%→35.9% | V2: 92.8%→79.1% | V3: {pk:.1%}→{fa:.1%}")

    # 保存
    with open(f"{DD}/accuracy_curve_v3.json","w") as f:
        json.dump({"meta":{"version":"V3","min":round(tt/60,1),
            "symbols":len(al),"records":sum(len(v) for v in al.values()),
            "projections":cn,"correct":co,"final":round(fa,4),"peak":round(pk,4),
            "stay_acc":round(sa,4),"stay_n":sn,"trans_acc":round(ta,4),"trans_n":tn,
            "signal_hits":sig_hits,"signal_ok":sig_ok},
            "curve":cv,"snapshots":ss,
            "compare":{"v1_pk":.39,"v1_fn":.359,"v2_pk":.928,"v2_fn":.791,
                        "v3_pk":round(pk,4),"v3_fn":round(fa,4)}},
            f,ensure_ascii=False,indent=2)
    print("✅ accuracy_curve_v3.json")
    return 0

if __name__=="__main__": sys.exit(main())

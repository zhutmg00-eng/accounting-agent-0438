export interface BeneishParams {
  curSales: number;
  prevSales: number;
  curAr: number;
  prevAr: number;
  curCogs: number;
  prevCogs: number;
  curAssets: number;
  prevAssets: number;
  curDepr: number;
  prevDepr: number;
  curPpe: number;
  prevPpe: number;
  curSga: number;
  prevSga: number;
  curLeverage: number;
  prevLeverage: number;
  curNetIncome: number;
  curCfo: number;
}

export function calculateBeneishMScore(params: BeneishParams) {
  const eps = 1e-6;
  const prevSales = Math.max(params.prevSales, eps);
  const curSales = Math.max(params.curSales, eps);
  const prevAssets = Math.max(params.prevAssets, eps);
  const curAssets = Math.max(params.curAssets, eps);

  // 1. DSRI
  const dsri = (params.curAr / curSales) / Math.max(params.prevAr / prevSales, eps);
  
  // 2. GMI
  const prevGm = (prevSales - params.prevCogs) / prevSales;
  const curGm = (curSales - params.curCogs) / curSales;
  const gmi = Math.max(prevGm, eps) / Math.max(curGm, eps);

  // 3. AQI
  const curAq = 1.0 - (params.curPpe / curAssets);
  const prevAq = 1.0 - (params.prevPpe / prevAssets);
  const aqi = Math.max(curAq, eps) / Math.max(prevAq, eps);

  // 4. SGI
  const sgi = curSales / prevSales;

  // 5. DEPI
  const curDeprRate = params.curDepr / Math.max(params.curPpe + params.curDepr, eps);
  const prevDeprRate = params.prevDepr / Math.max(params.prevPpe + params.prevDepr, eps);
  const depi = Math.max(prevDeprRate, eps) / Math.max(curDeprRate, eps);

  // 6. SGAI
  const sgai = (params.curSga / curSales) / Math.max(params.prevSga / prevSales, eps);

  // 7. LVGI
  const lvgi = params.curLeverage / Math.max(params.prevLeverage, eps);

  // 8. TATA
  const totalAccruals = params.curNetIncome - params.curCfo;
  const tata = totalAccruals / curAssets;

  const mScore = -4.84 +
    0.920 * dsri +
    0.528 * gmi +
    0.404 * aqi +
    0.892 * sgi +
    0.115 * depi -
    0.172 * sgai +
    4.037 * tata +
    0.0327 * lvgi;

  const isManipulator = mScore > -1.78;

  return {
    mScore: Number(mScore.toFixed(4)),
    isManipulator,
    variables: {
      DSRI: Number(dsri.toFixed(4)),
      GMI: Number(gmi.toFixed(4)),
      AQI: Number(aqi.toFixed(4)),
      SGI: Number(sgi.toFixed(4)),
      DEPI: Number(depi.toFixed(4)),
      SGAI: Number(sgai.toFixed(4)),
      LVGI: Number(lvgi.toFixed(4)),
      TATA: Number(tata.toFixed(4)),
    },
    conclusion: isManipulator
      ? "Beneish M-Score 超过 -1.78 预警线，财务报表存在重大利润操纵/舞弊嫌疑！"
      : "Beneish M-Score 处于安全区间，未见显著财务操纵特征。"
  };
}

/**
 * RetailGPT — Synthetic Data Generator (Node.js) v2
 * Calibrated CPG velocity, price, promo lift, and promo ROI ranges.
 * Source: Brad Pope / Perplexity calibration spec 2026-03-20
 *
 * Run: node scripts/generate_synthetic_data.js
 * Output: retailgpt_prototype.db in project root + CSVs in data/
 *
 * [SYNTHETIC DATA — DEMO ONLY]
 */

'use strict';

const Database = require('better-sqlite3');
const path = require('path');
const fs   = require('fs');

const DB_PATH  = path.join(__dirname, '..', 'retailgpt_prototype.db');
const DATA_DIR = path.join(__dirname, '..', 'data');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

// ─── Seeded PRNG (mulberry32) — deterministic output every run ────────────────
let _seed = 42;
function rand() {
  _seed |= 0; _seed = _seed + 0x6D2B79F5 | 0;
  let t = Math.imul(_seed ^ _seed >>> 15, 1 | _seed);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
  return ((t ^ t >>> 14) >>> 0) / 4294967296;
}
function randRange(lo, hi) { return lo + rand() * (hi - lo); }
function randInt(lo, hi)   { return Math.floor(lo + rand() * (hi - lo + 1)); }
function randChoice(arr)   { return arr[Math.floor(rand() * arr.length)]; }

// Box-Muller Gaussian (seeded)
function randGauss(mu, sigma) {
  const u1 = Math.max(rand(), 1e-10);
  const u2 = rand();
  return mu + sigma * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function randGaussClamp(mu, sigma, lo, hi) { return clamp(randGauss(mu, sigma), lo, hi); }

function weightedChoice(items, weights) {
  const total = weights.reduce((a, b) => a + b, 0);
  let r = rand() * total;
  for (let i = 0; i < items.length; i++) { r -= weights[i]; if (r <= 0) return items[i]; }
  return items[items.length - 1];
}

// ─── Brand calibration ────────────────────────────────────────────────────────
// Per Brad's Perplexity spec (2026-03-20)
const BRAND_PARAMS = {
  'Apex': {
    // Velocity: Normal(7, 3) clamped [1, 20]; hero items use higher end
    velMu: 7, velSd: 3, velLo: 1, velHi: 20,
    velHeroMu: 9, velHeroSd: 2,  // core SKUs skew higher
    velTailMu: 3.5, velTailSd: 1.5, velTailLo: 1, velTailHi: 7,
    // Price: Normal(4.0, 0.5) clamped [3, 5]
    priceMu: 4.0, priceSd: 0.5, priceLo: 3.0, priceHi: 5.0,
    // Promo lift: Normal(25, 10) clamped [8, 80]
    liftMu: 25, liftSd: 10, liftLo: 8, liftHi: 80,
    // Promo ROI bands: poor 0.3–0.8 (12%), typical 0.8–2.0 (75%), great 2.0–3.5 (13%)
    roiBands: [
      { lo: 0.3, hi: 0.8,  mu: 0.55, sd: 0.15, weight: 12 },
      { lo: 0.8, hi: 2.0,  mu: 1.40, sd: 0.30, weight: 75 },
      { lo: 2.0, hi: 3.5,  mu: 2.50, sd: 0.40, weight: 13 },
    ],
  },
  'Bolt': {
    // Velocity: Normal(12, 6) clamped [2, 40]
    velMu: 12, velSd: 6, velLo: 2, velHi: 40,
    velHeroMu: 16, velHeroSd: 5,
    velTailMu: 6, velTailSd: 2, velTailLo: 2, velTailHi: 12,
    // Price: Normal(2.75, 0.25) clamped [2, 3.5]
    priceMu: 2.75, priceSd: 0.25, priceLo: 2.0, priceHi: 3.5,
    // Promo lift: Normal(35, 15) clamped [10, 90]
    liftMu: 35, liftSd: 15, liftLo: 10, liftHi: 90,
    // Promo ROI bands: poor 0.5–1.0 (12%), typical 1.0–2.5 (75%), great 2.5–4.0 (13%)
    roiBands: [
      { lo: 0.5, hi: 1.0,  mu: 0.75, sd: 0.15, weight: 12 },
      { lo: 1.0, hi: 2.5,  mu: 1.75, sd: 0.35, weight: 75 },
      { lo: 2.5, hi: 4.0,  mu: 3.00, sd: 0.40, weight: 13 },
    ],
  },
  'Silke': {
    // Velocity: Normal(2, 1) clamped [0.3, 6]
    velMu: 2, velSd: 1, velLo: 0.3, velHi: 6,
    velHeroMu: 2.8, velHeroSd: 0.8,  // everyday shampoo/conditioner
    velTailMu: 0.9, velTailSd: 0.4, velTailLo: 0.3, velTailHi: 2.5, // treatments
    // Price: Normal(8.0, 1.5) clamped [5, 12]
    priceMu: 8.0, priceSd: 1.5, priceLo: 5.0, priceHi: 12.0,
    // Treatments skew higher: [8, 12]; everyday: [6, 10]
    priceTreatmentLo: 8.0, priceTreatmentHi: 12.0,
    priceEverydayLo:  6.0, priceEverydayHi: 10.0,
    // Promo lift: Normal(20, 8) clamped [8, 50]
    liftMu: 20, liftSd: 8, liftLo: 8, liftHi: 50,
    // Promo ROI bands: poor 0.3–0.7 (13%), typical 0.7–2.0 (74%), great 2.0–3.0 (13%)
    roiBands: [
      { lo: 0.3, hi: 0.7,  mu: 0.50, sd: 0.12, weight: 13 },
      { lo: 0.7, hi: 2.0,  mu: 1.35, sd: 0.30, weight: 74 },
      { lo: 2.0, hi: 3.0,  mu: 2.30, sd: 0.25, weight: 13 },
    ],
  },
};

function sampleROI(brandKey) {
  const params = BRAND_PARAMS[brandKey];
  const band = weightedChoice(params.roiBands, params.roiBands.map(b => b.weight));
  return clamp(randGauss(band.mu, band.sd), band.lo, band.hi);
}

// ─── Reference data ───────────────────────────────────────────────────────────
// Walmart-only dataset — this tool is built for a customer team calling on one retailer
const RETAILERS = ['Walmart'];
const REGIONS   = ['Southeast','Northeast','Midwest','West','South Central'];

const BRANDS = {
  'Apex': {
    category: 'Snacks', sub: 'Salty Snacks',
    stores: { Walmart:3800, Target:1600, Kroger:1200, Costco:550, Amazon:0, CVS:400, Walgreens:350, Albertsons:500 },
  },
  'Bolt': {
    category: 'Beverages', sub: 'Energy Drinks',
    stores: { Walmart:3600, Target:1500, Kroger:1100, Costco:480, Amazon:0, CVS:550, Walgreens:500, Albertsons:420 },
  },
  'Silke': {
    category: 'Personal Care', sub: 'Hair Care',
    stores: { Walmart:3200, Target:1800, Kroger:900, Costco:300, Amazon:0, CVS:700, Walgreens:650, Albertsons:380 },
  },
};

// SKU master — realistic product names + WMT item numbers
const SKU_MASTER = {
  'SKU-A01': { brand:'Apex',  desc:'Apex Original Sea Salt Thin Crisps 4oz',      upc:'0-72820-00101-4', wmt:'003825541', isHero:true,  isTreatment:false },
  'SKU-A02': { brand:'Apex',  desc:'Apex Bold BBQ Kettle Chips 8oz',               upc:'0-72820-00102-1', wmt:'003825542', isHero:true,  isTreatment:false },
  'SKU-A03': { brand:'Apex',  desc:'Apex Lite Veggie Straws 12oz',                 upc:'0-72820-00103-8', wmt:'003825543', isHero:true,  isTreatment:false },
  'SKU-A04': { brand:'Apex',  desc:'Apex Premium Aged Cheddar Puffs 16oz',         upc:'0-72820-00104-5', wmt:'003825544', isHero:false, isTreatment:false },
  'SKU-A05': { brand:'Apex',  desc:'Apex Classic White Cheddar Popcorn 24oz',      upc:'0-72820-00105-2', wmt:'003825545', isHero:false, isTreatment:false },
  'SKU-A06': { brand:'Apex',  desc:'Apex Pro Protein Pretzels 32oz',               upc:'0-72820-00106-9', wmt:'003825546', isHero:false, isTreatment:false },
  'SKU-A07': { brand:'Apex',  desc:'Apex Max Variety Pack 6ct',                    upc:'0-72820-00107-6', wmt:'003825547', isHero:false, isTreatment:false },
  'SKU-A08': { brand:'Apex',  desc:'Apex Pure Unsalted Rice Cakes 12pk',           upc:'0-72820-00108-3', wmt:'003825548', isHero:false, isTreatment:false },
  'SKU-A09': { brand:'Apex',  desc:'Apex Value Mix Party Pack 36oz',               upc:'0-72820-00109-0', wmt:'003825549', isHero:false, isTreatment:false },
  'SKU-A10': { brand:'Apex',  desc:'Apex XL Family Size Tortilla Chips 48oz',      upc:'0-72820-00110-6', wmt:'003825550', isHero:false, isTreatment:false },
  'SKU-B01': { brand:'Bolt',  desc:'Bolt Original Energy Drink 12oz Single',       upc:'0-61126-00201-3', wmt:'005519301', isHero:true,  isTreatment:false },
  'SKU-B02': { brand:'Bolt',  desc:'Bolt Zero Sugar Energy 16oz Can',              upc:'0-61126-00202-0', wmt:'005519302', isHero:true,  isTreatment:false },
  'SKU-B03': { brand:'Bolt',  desc:'Bolt Citrus Burst Energy 12oz Single',         upc:'0-61126-00203-7', wmt:'005519303', isHero:true,  isTreatment:false },
  'SKU-B04': { brand:'Bolt',  desc:'Bolt Blue Raspberry Energy 16oz Can',          upc:'0-61126-00204-4', wmt:'005519304', isHero:false, isTreatment:false },
  'SKU-B05': { brand:'Bolt',  desc:'Bolt Classic Energy Blend 24oz',               upc:'0-61126-00205-1', wmt:'005519305', isHero:false, isTreatment:false },
  'SKU-B06': { brand:'Bolt',  desc:'Bolt Pro Pre-Workout Energy 32oz',             upc:'0-61126-00206-8', wmt:'005519306', isHero:false, isTreatment:false },
  'SKU-B07': { brand:'Bolt',  desc:'Bolt Max Energy Variety 6pk 12oz',             upc:'0-61126-00207-5', wmt:'005519307', isHero:false, isTreatment:false },
  'SKU-B08': { brand:'Bolt',  desc:'Bolt Pure Sugar-Free Energy 12pk 12oz',        upc:'0-61126-00208-2', wmt:'005519308', isHero:false, isTreatment:false },
  'SKU-B09': { brand:'Bolt',  desc:'Bolt Value Energy Multipack 18pk',             upc:'0-61126-00209-9', wmt:'005519309', isHero:false, isTreatment:false },
  'SKU-B10': { brand:'Bolt',  desc:'Bolt XL Bulk Energy Can 128oz',                upc:'0-61126-00210-5', wmt:'005519310', isHero:false, isTreatment:false },
  'SKU-C01': { brand:'Silke', desc:'Silke Moisturizing Shampoo 8oz',               upc:'0-85931-00301-2', wmt:'007234101', isHero:true,  isTreatment:false },
  'SKU-C02': { brand:'Silke', desc:'Silke Volumizing Conditioner 12oz',            upc:'0-85931-00302-9', wmt:'007234102', isHero:true,  isTreatment:false },
  'SKU-C03': { brand:'Silke', desc:'Silke Lite Daily Shampoo 12oz',                upc:'0-85931-00303-6', wmt:'007234103', isHero:true,  isTreatment:false },
  'SKU-C04': { brand:'Silke', desc:'Silke Premium Repair Mask 16oz',               upc:'0-85931-00304-3', wmt:'007234104', isHero:false, isTreatment:true  },
  'SKU-C05': { brand:'Silke', desc:'Silke Classic 2-in-1 Shampoo+Cond 24oz',      upc:'0-85931-00305-0', wmt:'007234105', isHero:false, isTreatment:false },
  'SKU-C06': { brand:'Silke', desc:'Silke Pro Color-Protect Shampoo 32oz',         upc:'0-85931-00306-7', wmt:'007234106', isHero:false, isTreatment:false },
  'SKU-C07': { brand:'Silke', desc:'Silke Max Salon Kit Shampoo+Cond 6pk',         upc:'0-85931-00307-4', wmt:'007234107', isHero:false, isTreatment:true  },
  'SKU-C08': { brand:'Silke', desc:'Silke Pure Sulfate-Free Shampoo 12pk Travel',  upc:'0-85931-00308-1', wmt:'007234108', isHero:false, isTreatment:false },
  'SKU-C09': { brand:'Silke', desc:'Silke Value Bundle Shampoo+Cond+Mask',         upc:'0-85931-00309-8', wmt:'007234109', isHero:false, isTreatment:true  },
  'SKU-C10': { brand:'Silke', desc:'Silke XL Family Shampoo 48oz',                 upc:'0-85931-00310-4', wmt:'007234110', isHero:false, isTreatment:false },
};

// Sample calibrated baseline velocity for a SKU (before trend/season/region)
function sampleBaselineVelocity(skuId) {
  const sku    = SKU_MASTER[skuId];
  const brand  = sku.brand;
  const params = BRAND_PARAMS[brand];
  if (brand === 'Silke') {
    if (sku.isTreatment) return randGaussClamp(params.velTailMu, params.velTailSd, params.velTailLo, params.velTailHi);
    return sku.isHero ? randGaussClamp(params.velHeroMu, params.velHeroSd, 1.5, params.velHi)
                      : randGaussClamp(params.velMu, params.velSd, params.velLo, params.velHi);
  }
  return sku.isHero
    ? randGaussClamp(params.velHeroMu, params.velHeroSd, params.velLo + 1, params.velHi)
    : randGaussClamp(params.velTailMu, params.velTailSd, params.velTailLo, params.velTailHi);
}

// Sample calibrated base price for a SKU
function sampleBasePrice(skuId) {
  const sku    = SKU_MASTER[skuId];
  const brand  = sku.brand;
  const params = BRAND_PARAMS[brand];
  if (brand === 'Silke') {
    const lo = sku.isTreatment ? params.priceTreatmentLo : params.priceEverydayLo;
    const hi = sku.isTreatment ? params.priceTreatmentHi : params.priceEverydayHi;
    return randGaussClamp(params.priceMu, params.priceSd, lo, hi);
  }
  return randGaussClamp(params.priceMu, params.priceSd, params.priceLo, params.priceHi);
}

// Sample promo lift % for a SKU
function samplePromoLift(skuId) {
  const brand  = SKU_MASTER[skuId].brand;
  const params = BRAND_PARAMS[brand];
  return randGaussClamp(params.liftMu, params.liftSd, params.liftLo, params.liftHi);
}

// ─── Week dates: Jan 2023 – Feb 2025 (Saturdays) ─────────────────────────────
function getSaturdayDates(start, end) {
  const dates = [];
  let d = new Date(start);
  while (d.getDay() !== 6) d.setDate(d.getDate() + 1);
  while (d <= end) { dates.push(new Date(d)); d.setDate(d.getDate() + 7); }
  return dates;
}
const WEEKS = getSaturdayDates(new Date('2023-01-07'), new Date('2025-02-22'));

function fmtDate(d) { return d.toISOString().slice(0, 10); }
function fmtTs(d)   { return d.toISOString().slice(0, 19).replace('T', ' '); }

console.log(`Generating ${WEEKS.length} weeks (${fmtDate(WEEKS[0])} → ${fmtDate(WEEKS[WEEKS.length-1])})`);

// ─── Seasonal index ───────────────────────────────────────────────────────────
function seasonalIndex(d) {
  const dayOfYear = Math.floor((d - new Date(d.getFullYear(), 0, 0)) / 86400000);
  const w = dayOfYear / 7;
  const summer  = 0.12 * Math.sin(Math.PI * (w - 10) / 26);
  const holiday = w > 38 ? 0.18 * Math.sin(Math.PI * (w - 38) / 16) : 0;
  return 1.0 + summer + holiday;
}

function growthTrend(d) {
  const weeksSinceStart = (d - new Date('2023-01-01')) / (7 * 86400000);
  return 1.0 + (0.08 / 52) * weeksSinceStart + randGauss(0, 0.004);
}

// ─── Promo schedule ───────────────────────────────────────────────────────────
const PROMO_TYPES   = ['TPR', 'Feature', 'Display', 'Feature+Display', 'BOGO'];
const PROMO_WEIGHTS = [0.38, 0.22, 0.17, 0.15, 0.08];

const PROMOS = [];
let promoCounter = 1;

// Pre-compute stable per-SKU baseline velocity (used in promo schedule)
const SKU_BASELINE_VEL   = {};
const SKU_BASELINE_PRICE = {};
for (const skuId of Object.keys(SKU_MASTER)) {
  SKU_BASELINE_VEL[skuId]   = sampleBaselineVelocity(skuId);
  SKU_BASELINE_PRICE[skuId] = sampleBasePrice(skuId);
}

for (const year of [2023, 2024, 2025]) {
  for (const [brandName] of Object.entries(BRANDS)) {
    const heroSkus = Object.keys(SKU_MASTER).filter(k => SKU_MASTER[k].brand === brandName && SKU_MASTER[k].isHero);
    for (const retailer of ['Walmart']) {
      const nPromos = randInt(5, 8);
      const usedStarts = [];
      for (let attempt = 0; attempt < nPromos * 6 && usedStarts.length < nPromos; attempt++) {
        const startWeek = randInt(1, 49);
        let startD = new Date(year, 0, 1);
        startD.setDate(startD.getDate() + startWeek * 7);
        while (startD.getDay() !== 6) startD.setDate(startD.getDate() + 1);
        const endD = new Date(startD); endD.setDate(endD.getDate() + 13);
        if (endD.getFullYear() > year) continue;
        if (usedStarts.some(s => Math.abs((startD - s) / 86400000) < 14)) continue;
        usedStarts.push(startD);

        const skuId    = randChoice(heroSkus);
        const promoType = weightedChoice(PROMO_TYPES, PROMO_WEIGHTS);
        const depth    = promoType === 'BOGO' ? 50 : randGaussClamp(22, 8, 10, 40);
        const baseVel  = SKU_BASELINE_VEL[skuId];
        const liftPct  = samplePromoLift(skuId);
        const promoVel = clamp(baseVel * (1 + liftPct / 100), 0, 40); // hard cap per spec
        const stores   = BRANDS[brandName].stores[retailer] * randGaussClamp(0.75, 0.1, 0.5, 1.0);
        const incrUnits = Math.max(0, Math.round((promoVel - baseVel) * stores * 2));
        const basePrice = SKU_BASELINE_PRICE[skuId];
        const tradeSpend = incrUnits * basePrice * randGaussClamp(0.18, 0.05, 0.08, 0.35);
        const roi = sampleROI(brandName);

        PROMOS.push({
          promo_id: `PROMO-${year}-${String(promoCounter).padStart(4, '0')}`,
          retailer_name: retailer, sku_id: skuId,
          promo_start_date: fmtDate(startD), promo_end_date: fmtDate(endD),
          promo_type: promoType,
          promo_depth_pct: +depth.toFixed(2),
          baseline_velocity: +baseVel.toFixed(2),
          promo_velocity: +promoVel.toFixed(2),
          promo_lift_pct: +liftPct.toFixed(2),
          incremental_units: incrUnits,
          cannibalization_rate_pct: +randGaussClamp(5, 4, 0, 20).toFixed(2),
          promo_roi: +roi.toFixed(2),
          trade_spend_dollars: +Math.max(tradeSpend, 2000).toFixed(2),
        });
        promoCounter++;
      }
    }
  }
}
console.log(`Generated ${PROMOS.length} promo events`);

function getActivePromo(skuId, retailer, weekDate) {
  const ds = fmtDate(weekDate);
  return PROMOS.find(p =>
    p.sku_id === skuId && p.retailer_name === retailer &&
    p.promo_start_date <= ds && ds <= p.promo_end_date) || null;
}

// ─── Generate sales rows ───────────────────────────────────────────────────────
function generateSales() {
  const rows = [];
  const regionMult = { Southeast:1.05, Northeast:0.95, Midwest:1.00, West:1.10, 'South Central':0.92 };

  for (const weekDate of WEEKS) {
    const season = seasonalIndex(weekDate);
    const trend  = growthTrend(weekDate);

    for (const [skuId, sku] of Object.entries(SKU_MASTER)) {
      const brand = BRANDS[sku.brand];

      for (const retailer of RETAILERS) {
        if (retailer === 'Amazon' && sku.brand !== 'Bolt' && rand() < 0.7) continue;
        const baseStores = brand.stores[retailer];
        if (!baseStores || baseStores < 50) continue;

        for (const region of REGIONS) {
          const rm     = regionMult[region];
          const stores = Math.round(baseStores * rm / REGIONS.length * randGaussClamp(1.0, 0.08, 0.80, 1.20));
          if (stores < 20) continue;

          // Calibrated base velocity (per-SKU, stable anchor)
          const baseVel   = SKU_BASELINE_VEL[skuId];
          const basePrice = SKU_BASELINE_PRICE[skuId];

          // Apply trend, season, region, weekly noise
          let vel   = baseVel  * trend * season * rm * randGaussClamp(1.0, 0.08, 0.80, 1.25);
          let price = basePrice * randGaussClamp(1.0, 0.03, 0.92, 1.08); // small weekly price noise

          // Promo override
          const promo = getActivePromo(skuId, retailer, weekDate);
          if (promo) {
            vel   = clamp(promo.promo_velocity * rm * randGaussClamp(1.0, 0.06, 0.88, 1.12), 0.1, 40);
            price = price * (1 - promo.promo_depth_pct / 100);
          }

          const units       = Math.max(1, Math.round(vel * stores));
          const dollars     = +(units * price).toFixed(2);
          const velPerStore = +(vel).toFixed(3);

          // OOS: base ~2-3%, spikes during promos
          let oos = randGaussClamp(2.5, 1.2, 0.5, 6.0);
          if (promo) oos = Math.min(oos + randGaussClamp(3, 2, 0, 8), 20);
          if (rand() < 0.02) oos = Math.min(oos + randRange(5, 14), 25); // rare supply event

          // Prior year baseline (strip trend back ~8%)
          const pyVel   = baseVel * seasonalIndex(new Date(weekDate.getTime() - 52 * 7 * 86400000)) * rm;
          const pyUnits = Math.max(1, Math.round(pyVel * stores * 0.93));
          const pySales = +(pyUnits * basePrice).toFixed(2);
          const yoy     = +((dollars - pySales) / Math.max(pySales, 1) * 100).toFixed(2);

          rows.push({
            week_ending_date: fmtDate(weekDate),
            retailer_name: retailer,
            wmt_item_number: retailer === 'Walmart' ? sku.wmt : null,
            region,
            brand_name: sku.brand,
            category: brand.category,
            sub_category: brand.sub,
            sku_id: skuId,
            sku_description: sku.desc,
            upc: sku.upc,
            dollar_sales: dollars,
            unit_sales: units,
            velocity_per_store: velPerStore,
            avg_selling_price: +price.toFixed(2),
            num_stores_selling: stores,
            acv_distribution_pct: +clamp(randGauss(72, 7), 40, 96).toFixed(2),
            oos_rate_pct: +oos.toFixed(2),
            prior_year_dollar_sales: pySales,
            prior_year_unit_sales: pyUnits,
            yoy_dollar_growth_pct: yoy,
          });
        }
      }
    }
  }
  return rows;
}

// ─── Scorecards ───────────────────────────────────────────────────────────────
function generateScorecards() {
  const periods = ['2023-Q1','2023-Q2','2023-Q3','2023-Q4','2024-Q1','2024-Q2','2024-Q3','2024-Q4','2025-Q1'];
  const buyers  = {
    Walmart:'Jennifer Martinez', Target:'Michael Chen', Kroger:'Sarah Johnson',
    Costco:'David Kim', Amazon:'Rachel Thompson', CVS:'James Williams',
    Walgreens:'Emily Davis', Albertsons:'Robert Wilson',
  };
  const rows = [];
  for (const period of periods) {
    const year  = parseInt(period);
    const trend = 1 + 0.08 * (year - 2023);
    for (const [brandName, info] of Object.entries(BRANDS)) {
      for (const retailer of RETAILERS) {
        if (!info.stores[retailer] || info.stores[retailer] < 100) continue;
        // Use calibrated velocity × stores × price × 13 weeks for base
        const skusForBrand = Object.values(SKU_MASTER).filter(s => s.brand === brandName);
        const avgVel   = skusForBrand.reduce((a, s) => a + SKU_BASELINE_VEL[s.brand === brandName ? Object.keys(SKU_MASTER).find(k => SKU_MASTER[k] === s) : ''], 0);
        const params   = BRAND_PARAMS[brandName];
        const baseVel  = randGaussClamp(params.velMu, params.velSd, params.velLo, params.velHi);
        const basePrice = randGaussClamp(params.priceMu, params.priceSd, params.priceLo, params.priceHi);
        const base     = info.stores[retailer] * baseVel * basePrice * 13;
        rows.push({
          scorecard_period: period, retailer_name: retailer, brand_name: brandName,
          total_dollar_sales: +(base * trend * randGaussClamp(1, 0.08, 0.82, 1.18)).toFixed(2),
          dollar_share_of_category_pct: +randGaussClamp(8, 4, 2, 25).toFixed(2),
          distribution_points: randInt(8, 28),
          avg_acv_pct: +randGaussClamp(70, 8, 48, 92).toFixed(2),
          avg_oos_rate_pct: +randGaussClamp(3, 1.2, 1, 9).toFixed(2),
          total_promo_weeks: randInt(4, 18),
          on_shelf_availability_pct: +randGaussClamp(95, 2, 88, 99.5).toFixed(2),
          yoy_sales_growth_pct: +randGaussClamp(8, 5, -5, 25).toFixed(2),
          new_items_added: randInt(0, 4),
          items_delisted: randInt(0, 2),
          buyer_name: buyers[retailer],
          jbp_target_growth_pct: +randGaussClamp(8, 2, 4, 15).toFixed(2),
        });
      }
    }
  }
  return rows;
}

// ─── Alerts ───────────────────────────────────────────────────────────────────
function generateAlerts() {
  const rows = [];
  const allSkuIds      = Object.keys(SKU_MASTER);
  const eligibleWeeks  = WEEKS.filter(w => w >= new Date('2023-06-01'));
  const statuses       = ['Open','Open','Open','Acknowledged','Assigned','Resolved'];
  const assignees      = ['john.smith@company.com','sarah.jones@company.com','mike.chen@company.com'];
  const types = [
    { type:'OOS_BREACH',       sev:'High',   tmpl:'OOS rate {a}% at {r} exceeded {t}% threshold for {s}. Promotional demand spike may have depleted DC safety stock.' },
    { type:'VELOCITY_DECLINE', sev:'Medium', tmpl:'Velocity for {s} at {r} declined {a}% week-over-week vs. {t}% alert threshold. Possible competitive distribution gain or shelf reset.' },
    { type:'PROMO_ROI_MISS',   sev:'Medium', tmpl:'Promo ROI for {s} at {r} came in at {a}x vs. {t}x target. Trade spend efficiency is below breakeven.' },
    { type:'DISTRIBUTION_LOSS',sev:'Low',    tmpl:'ACV distribution for {s} at {r} dropped {a} points vs. prior period. Verify item status and planogram compliance with buyer.' },
  ];
  const thresholds = { OOS_BREACH:5.0, VELOCITY_DECLINE:10.0, PROMO_ROI_MISS:1.0, DISTRIBUTION_LOSS:5.0 };

  for (let i = 0; i < 120; i++) {
    const { type, sev, tmpl } = randChoice(types);
    const skuId    = randChoice(allSkuIds);
    const retailer = 'Walmart';
    const alertDate = randChoice(eligibleWeeks);
    const threshold = thresholds[type];
    const actual    = type === 'PROMO_ROI_MISS'
      ? +randGaussClamp(0.4, 0.2, 0.1, 0.95).toFixed(2)
      : +(threshold + randGaussClamp(3, 2, 0.5, 14)).toFixed(2);
    const status    = randChoice(statuses);
    const narrative = tmpl.replace('{a}', actual).replace('{r}', retailer)
                          .replace('{t}', threshold).replace('{s}', SKU_MASTER[skuId].desc);
    const assignedTo    = ['Assigned','Resolved'].includes(status) ? randChoice(assignees) : null;
    const resolvedTs    = status === 'Resolved'
      ? fmtTs(new Date(alertDate.getTime() + randInt(1, 5) * 86400000)) : null;

    rows.push({
      alert_id: `ALERT-${fmtDate(alertDate).replace(/-/g,'')}-${String(i+1).padStart(4,'0')}`,
      alert_timestamp: fmtTs(new Date(alertDate.getFullYear(), alertDate.getMonth(), alertDate.getDate(), 8, 0)),
      alert_type: type, severity: sev,
      sku_id: skuId, retailer_name: retailer,
      metric_name: type.replace(/_/g, ' '),
      threshold_value: threshold, actual_value: actual,
      root_cause_narrative: narrative,
      status, assigned_to: assignedTo,
      assignment_comment: assignedTo ? 'Please review and take action.' : null,
      resolved_timestamp: resolvedTs,
    });
  }
  return rows;
}

// ─── Users ────────────────────────────────────────────────────────────────────
const USERS = [
  { user_id:'USR-001', user_name:'Sarah Johnson',  user_email:'sarah.johnson@company.com',  user_role:'Brand Manager',      default_narrative_mode:'Merchant',  priority_metrics:'Revenue,Velocity,OOS Rate',                      retailer_scope:'Walmart', region_scope:'', brand_scope:'Apex',     excluded_regions:'', oos_alert_threshold_pct:5.00, velocity_decline_threshold_pct:10.00, promo_roi_floor:0.80, preferred_time_period:'L4W',  email_report_cadence:'Weekly' },
  { user_id:'USR-002', user_name:'Michael Chen',   user_email:'michael.chen@company.com',   user_role:'Sales Director',     default_narrative_mode:'Executive', priority_metrics:'Revenue,Promo Lift,Distribution Points',         retailer_scope:'Walmart', region_scope:'', brand_scope:'',         excluded_regions:'', oos_alert_threshold_pct:7.00, velocity_decline_threshold_pct:15.00, promo_roi_floor:1.00, preferred_time_period:'L13W', email_report_cadence:'Weekly' },
  { user_id:'USR-003', user_name:'Rachel Thompson',user_email:'rachel.thompson@company.com',user_role:'Category Analyst',   default_narrative_mode:'Analyst',   priority_metrics:'Velocity,OOS Rate,ACV,Promo ROI',                retailer_scope:'Walmart', region_scope:'', brand_scope:'Bolt',     excluded_regions:'', oos_alert_threshold_pct:4.00, velocity_decline_threshold_pct:8.00,  promo_roi_floor:0.90, preferred_time_period:'L4W',  email_report_cadence:'Daily'  },
  { user_id:'USR-004', user_name:'David Park',     user_email:'david.park@company.com',     user_role:'Account Manager',    default_narrative_mode:'Merchant',  priority_metrics:'Revenue,OOS Rate,Promo ROI',                     retailer_scope:'Walmart', region_scope:'', brand_scope:'Silke',    excluded_regions:'', oos_alert_threshold_pct:6.00, velocity_decline_threshold_pct:12.00, promo_roi_floor:0.75, preferred_time_period:'L4W',  email_report_cadence:'Weekly' },
  { user_id:'USR-005', user_name:'Jennifer Walsh', user_email:'jennifer.walsh@company.com', user_role:'VP Sales',           default_narrative_mode:'Executive', priority_metrics:'Revenue,Velocity,Promo Lift,OOS Rate',           retailer_scope:'Walmart', region_scope:'', brand_scope:'',         excluded_regions:'', oos_alert_threshold_pct:5.00, velocity_decline_threshold_pct:10.00, promo_roi_floor:0.85, preferred_time_period:'YTD',  email_report_cadence:'Weekly' },
];

// ─── Create DB + seed ─────────────────────────────────────────────────────────
// Drop and recreate to pick up wmt_item_number column in sales table
const db = new Database(DB_PATH);

db.exec(`
DROP TABLE IF EXISTS sales_kpi_weekly;
DROP TABLE IF EXISTS promo_calendar;
DROP TABLE IF EXISTS retailer_account_scorecard;
DROP TABLE IF EXISTS kpi_alert_log;
DROP TABLE IF EXISTS user_preferences;
DROP TABLE IF EXISTS metric_store;
DROP TABLE IF EXISTS benchmark_reference;
DROP TABLE IF EXISTS supply_chain_weekly;

CREATE TABLE sales_kpi_weekly (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  week_ending_date TEXT, retailer_name TEXT, wmt_item_number TEXT,
  region TEXT, brand_name TEXT, category TEXT, sub_category TEXT,
  sku_id TEXT, sku_description TEXT, upc TEXT,
  dollar_sales REAL, unit_sales INTEGER, velocity_per_store REAL,
  avg_selling_price REAL, num_stores_selling INTEGER,
  acv_distribution_pct REAL, oos_rate_pct REAL,
  prior_year_dollar_sales REAL, prior_year_unit_sales INTEGER, yoy_dollar_growth_pct REAL
);
CREATE TABLE promo_calendar (
  promo_id TEXT PRIMARY KEY, retailer_name TEXT, sku_id TEXT,
  promo_start_date TEXT, promo_end_date TEXT, promo_type TEXT,
  promo_depth_pct REAL, baseline_velocity REAL, promo_velocity REAL,
  promo_lift_pct REAL, incremental_units INTEGER,
  cannibalization_rate_pct REAL, promo_roi REAL, trade_spend_dollars REAL
);
CREATE TABLE retailer_account_scorecard (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scorecard_period TEXT, retailer_name TEXT, brand_name TEXT,
  total_dollar_sales REAL, dollar_share_of_category_pct REAL,
  distribution_points INTEGER, avg_acv_pct REAL, avg_oos_rate_pct REAL,
  total_promo_weeks INTEGER, on_shelf_availability_pct REAL,
  yoy_sales_growth_pct REAL, new_items_added INTEGER, items_delisted INTEGER,
  buyer_name TEXT, jbp_target_growth_pct REAL
);
CREATE TABLE kpi_alert_log (
  alert_id TEXT PRIMARY KEY, alert_timestamp TEXT, alert_type TEXT,
  severity TEXT, sku_id TEXT, retailer_name TEXT, metric_name TEXT,
  threshold_value REAL, actual_value REAL, root_cause_narrative TEXT,
  status TEXT, assigned_to TEXT, assignment_comment TEXT, resolved_timestamp TEXT
);
CREATE TABLE user_preferences (
  user_id TEXT PRIMARY KEY, user_name TEXT, user_email TEXT, user_role TEXT,
  default_narrative_mode TEXT, priority_metrics TEXT, retailer_scope TEXT,
  region_scope TEXT, brand_scope TEXT, excluded_regions TEXT,
  oos_alert_threshold_pct REAL, velocity_decline_threshold_pct REAL,
  promo_roi_floor REAL, preferred_time_period TEXT, email_report_cadence TEXT
);

CREATE TABLE benchmark_reference (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  brand_name TEXT,              -- NULL = applies to all brands in category
  category TEXT,
  metric_name TEXT,
  tier_weak REAL,               -- below this = weak
  tier_avg_low REAL,
  tier_avg_high REAL,
  tier_strong REAL,             -- above this = strong
  tier_elite REAL,
  unit TEXT,
  interpretation_weak TEXT,
  interpretation_avg TEXT,
  interpretation_strong TEXT,
  interpretation_action_weak TEXT,
  walmart_threshold REAL,
  walmart_threshold_note TEXT
);

CREATE TABLE supply_chain_weekly (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  week_ending_date TEXT,
  retailer_name TEXT,
  brand_name TEXT,
  otif_rate_pct REAL,           -- On-Time In-Full %
  dc_fill_rate_pct REAL,        -- DC Fill Rate %
  case_fill_rate_pct REAL,      -- Supplier Case Fill %
  on_time_delivery_pct REAL,    -- On-Time component
  in_full_delivery_pct REAL,    -- In-Full component
  chargebacks_dollars REAL,     -- OTIF fines for the week
  compliance_score REAL         -- SQEP compliance 0-100
);

CREATE TABLE metric_store (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  computed_at TEXT,
  period_label TEXT,        -- L4W, L13W, L52W, YTD
  period_start_date TEXT,
  period_end_date TEXT,
  num_weeks INTEGER,
  grain TEXT,               -- total | brand | sku | region
  retailer_name TEXT,
  brand_name TEXT,          -- NULL at total grain
  sku_id TEXT,              -- NULL unless grain=sku
  sku_description TEXT,     -- NULL unless grain=sku
  region TEXT,              -- NULL unless grain=region

  -- Volume & Revenue
  revenue REAL,
  units_sold REAL,
  num_stores_selling INTEGER,
  avg_selling_price REAL,

  -- Velocity (U/S/W — the primary CPG metric)
  velocity_units_per_store_per_week REAL,

  -- Distribution
  avg_acv_pct REAL,
  distribution_points INTEGER,

  -- Shelf health
  avg_oos_rate_pct REAL,

  -- YoY comparison (same period prior year)
  revenue_prior_year REAL,
  units_prior_year REAL,
  velocity_prior_year REAL,
  revenue_yoy_pct REAL,
  velocity_yoy_pct REAL,

  -- Promo performance (NULLs if no promos in period)
  promo_events INTEGER,
  avg_promo_lift_pct REAL,
  avg_promo_roi REAL,
  total_trade_spend REAL,

  -- Benchmark flags (set vs. category thresholds)
  oos_above_threshold INTEGER,   -- 1 if avg_oos > 5%
  velocity_trend TEXT,           -- up | flat | down vs prior period
  UNIQUE(period_label, grain, retailer_name, brand_name, sku_id, region)
);
`);

function bulkInsert(table, rows, batchSize = 500) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const stmt = db.prepare(`INSERT OR REPLACE INTO ${table} (${cols.join(',')}) VALUES (${cols.map(() => '?').join(',')})`);
  const insertMany = db.transaction(batch => { for (const r of batch) stmt.run(Object.values(r)); });
  for (let i = 0; i < rows.length; i += batchSize) {
    insertMany(rows.slice(i, i + batchSize));
    if (i % 20000 === 0 && i > 0) process.stdout.write(`  ... ${i.toLocaleString()} / ${rows.length.toLocaleString()}\n`);
  }
}

console.log('Seeding user_preferences...');
bulkInsert('user_preferences', USERS);
console.log(`  ✅ ${USERS.length} users`);

console.log('Seeding promo_calendar...');
bulkInsert('promo_calendar', PROMOS);
console.log(`  ✅ ${PROMOS.length} promos`);

console.log('Generating sales_kpi_weekly...');
const salesRows = generateSales();
console.log(`  Generated ${salesRows.length.toLocaleString()} rows — inserting...`);
bulkInsert('sales_kpi_weekly', salesRows);
console.log(`  ✅ ${salesRows.length.toLocaleString()} sales rows`);

console.log('Seeding retailer_account_scorecard...');
const scorecards = generateScorecards();
bulkInsert('retailer_account_scorecard', scorecards);
console.log(`  ✅ ${scorecards.length} scorecard rows`);

console.log('Seeding kpi_alert_log...');
const alerts = generateAlerts();
bulkInsert('kpi_alert_log', alerts);
console.log(`  ✅ ${alerts.length} alerts`);

// ─── Export CSVs ──────────────────────────────────────────────────────────────
function writeCsv(filepath, rows) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const lines = [cols.join(',')];
  for (const r of rows) {
    lines.push(cols.map(c => {
      const v = r[c];
      if (v === null || v === undefined) return '';
      const s = String(v);
      return (s.includes(',') || s.includes('"') || s.includes('\n'))
        ? '"' + s.replace(/"/g, '""') + '"' : s;
    }).join(','));
  }
  fs.writeFileSync(filepath, lines.join('\n'), 'utf8');
}

console.log('\nExporting Walmart CSVs...');

// Sales: Walmart only, all columns
const wmtSales = db.prepare(`
  SELECT week_ending_date, retailer_name, wmt_item_number, region,
         brand_name, category, sub_category, sku_id, sku_description, upc,
         dollar_sales, unit_sales, velocity_per_store, avg_selling_price,
         num_stores_selling, acv_distribution_pct, oos_rate_pct,
         prior_year_dollar_sales, prior_year_unit_sales, yoy_dollar_growth_pct
  FROM sales_kpi_weekly WHERE retailer_name='Walmart'
  ORDER BY week_ending_date DESC, sku_id, region
`).all();
writeCsv(`${DATA_DIR}/walmart_sales_kpi_weekly_full.csv`, wmtSales);
console.log(`  ✅ walmart_sales_kpi_weekly_full.csv — ${wmtSales.length.toLocaleString()} rows`);

// Promos: Walmart only
const wmtPromos = db.prepare(`SELECT * FROM promo_calendar WHERE retailer_name='Walmart' ORDER BY promo_start_date DESC`).all();
writeCsv(`${DATA_DIR}/walmart_promo_calendar.csv`, wmtPromos);
console.log(`  ✅ walmart_promo_calendar.csv — ${wmtPromos.length} rows`);

// Scorecards: Walmart only
const wmtScores = db.prepare(`SELECT scorecard_period,retailer_name,brand_name,total_dollar_sales,dollar_share_of_category_pct,distribution_points,avg_acv_pct,avg_oos_rate_pct,total_promo_weeks,on_shelf_availability_pct,yoy_sales_growth_pct,new_items_added,items_delisted,buyer_name,jbp_target_growth_pct FROM retailer_account_scorecard WHERE retailer_name='Walmart' ORDER BY scorecard_period DESC, brand_name`).all();
writeCsv(`${DATA_DIR}/walmart_account_scorecard.csv`, wmtScores);
console.log(`  ✅ walmart_account_scorecard.csv — ${wmtScores.length} rows`);

// Alerts: Walmart only
const wmtAlerts = db.prepare(`SELECT alert_id,alert_timestamp,alert_type,severity,sku_id,retailer_name,metric_name,threshold_value,actual_value,root_cause_narrative,status,assigned_to,assignment_comment,resolved_timestamp FROM kpi_alert_log WHERE retailer_name='Walmart' ORDER BY alert_timestamp DESC`).all();
writeCsv(`${DATA_DIR}/walmart_kpi_alert_log.csv`, wmtAlerts);
console.log(`  ✅ walmart_kpi_alert_log.csv — ${wmtAlerts.length} rows`);

// SKU reference
const skuRef = Object.entries(SKU_MASTER).map(([skuId, s]) => ({
  sku_id: skuId, wmt_item_number: s.wmt, sku_description: s.desc, upc: s.upc,
  brand_name: s.brand, category: BRANDS[s.brand].category, sub_category: BRANDS[s.brand].sub,
  is_hero: s.isHero ? 'Y' : 'N', is_treatment: s.isTreatment ? 'Y' : 'N',
}));
writeCsv(`${DATA_DIR}/sku_reference.csv`, skuRef);
console.log(`  ✅ sku_reference.csv — ${skuRef.length} items`);

// Sanity check
// ─── Benchmark Reference Data ────────────────────────────────────────────────
console.log('\nSeeding benchmark reference...');
const benchmarks = [
  // Velocity benchmarks — brand-specific
  { brand_name:'Apex',  category:'Salty Snacks',   metric_name:'velocity',  tier_weak:3.0,  tier_avg_low:3.0,  tier_avg_high:6.0,  tier_strong:6.0,  tier_elite:10.0, unit:'U/S/W', interpretation_weak:'Below avg for salty snacks at Walmart — delistment risk if sustained below 3.0 U/S/W', interpretation_avg:'In line with Walmart salty snacks average velocity range', interpretation_strong:'Above average — strong shelf productivity; buyer will want to expand facings', interpretation_action_weak:'Investigate distribution gaps, phantom inventory, and competitive pricing. Prepare corrective action plan for buyer.', walmart_threshold:null, walmart_threshold_note:null },
  { brand_name:'Bolt',  category:'Energy Drinks',  metric_name:'velocity',  tier_weak:5.0,  tier_avg_low:5.0,  tier_avg_high:10.0, tier_strong:10.0, tier_elite:16.0, unit:'U/S/W', interpretation_weak:'Below avg for energy drinks — energy is a high-velocity category; weak performance here draws buyer scrutiny quickly', interpretation_avg:'Tracking with Walmart energy drinks average', interpretation_strong:'Strong velocity — energy drinks category leader territory', interpretation_action_weak:'Energy drinks should drive >10 U/S/W for core SKUs. Check price competitiveness vs Monster/Red Bull and display execution.', walmart_threshold:null, walmart_threshold_note:null },
  { brand_name:'Silke', category:'Hair Care',       metric_name:'velocity',  tier_weak:1.5,  tier_avg_low:1.5,  tier_avg_high:3.0,  tier_strong:3.0,  tier_elite:5.0,  unit:'U/S/W', interpretation_weak:'Below avg for hair care — category is lower velocity than food; however below 1.5 signals shelf productivity issue', interpretation_avg:'In line with hair care average velocity at Walmart', interpretation_strong:'Strong for hair care — likely a hero SKU with strong household penetration', interpretation_action_weak:'Review planogram placement (eye-level vs. bottom shelf), shade/variant assortment, and promotional frequency.', walmart_threshold:null, walmart_threshold_note:null },

  // OOS Rate — applies to all brands
  { brand_name:null, category:'All',    metric_name:'oos_rate',  tier_weak:8.0,  tier_avg_low:3.0, tier_avg_high:5.0, tier_strong:3.0, tier_elite:1.5, unit:'%', interpretation_weak:'Critical OOS — above 8% triggers Walmart replenishment review. Buyer visibility is near-certain.', interpretation_avg:'Elevated but manageable — above 3% warrants root cause investigation', interpretation_strong:'Healthy OOS rate — shelf availability meeting Walmart expectations', interpretation_action_weak:'Identify if OOS is DC-side (case fill/OTIF issue) or store-side (phantom inventory/replenishment cycle). Engage Walmart supply chain team.', walmart_threshold:5.0, walmart_threshold_note:'Above 5% triggers buyer monitoring; above 8% risks replenishment reduction; above 12% risks delistment at next modular review' },

  // Promo ROI — all brands
  { brand_name:null, category:'All',    metric_name:'promo_roi', tier_weak:1.0,  tier_avg_low:1.0, tier_avg_high:1.8, tier_strong:1.8, tier_elite:2.5, unit:'x', interpretation_weak:'Below breakeven — trade spend is not generating incremental profit. This promotion is losing money.', interpretation_avg:'Acceptable ROI range — profitable but room to optimize promo depth or mechanics', interpretation_strong:'Strong promo ROI — trade investment is working efficiently', interpretation_action_weak:'Reduce promo depth or frequency. If strategic (new item trial), establish an exit plan with a defined velocity threshold.', walmart_threshold:null, walmart_threshold_note:null },

  // Promo Lift — all brands
  { brand_name:null, category:'All',    metric_name:'promo_lift', tier_weak:15.0, tier_avg_low:15.0, tier_avg_high:40.0, tier_strong:40.0, tier_elite:70.0, unit:'%', interpretation_weak:'Low promo lift — consumers not responding to the promotion. Possible causes: insufficient depth, poor feature/display, or category fatigue.', interpretation_avg:'Average promo response — promotion is working but not a standout event', interpretation_strong:'Strong lift — promotion is driving meaningful volume. Verify supply chain was ready for demand.', interpretation_action_weak:'Review promo mechanics: depth (is TPR deep enough?), feature/display execution (are you getting secondary placement?), and timing (competitive overlap?).', walmart_threshold:null, walmart_threshold_note:null },

  // OTIF
  { brand_name:null, category:'All',    metric_name:'otif',      tier_weak:95.0, tier_avg_low:95.0, tier_avg_high:98.0, tier_strong:98.0, tier_elite:99.5, unit:'%', interpretation_weak:'Below 95% OTIF — Walmart is actively charging 3% cost-of-goods fines on affected POs. Immediate supply chain review required.', interpretation_avg:'Below target — OTIF between 95-98% puts you in fine risk territory and triggers buyer monitoring', interpretation_strong:'Compliant — meeting Walmart\'s 98% OTIF target', interpretation_action_weak:'Review PO lead times, carrier performance, and DC fill rates. Escalate with Walmart supply chain team immediately.', walmart_threshold:98.0, walmart_threshold_note:'Below 98% = monitoring; below 95% = 3% cost-of-goods fine per PO; chronic non-compliance risks supply chain sanctions' },

  // DC Fill Rate
  { brand_name:null, category:'All',    metric_name:'dc_fill_rate', tier_weak:93.0, tier_avg_low:93.0, tier_avg_high:97.0, tier_strong:97.0, tier_elite:99.0, unit:'%', interpretation_weak:'DC fill below 93% — you are failing to ship what Walmart ordered. This is the root cause of store-level OOS.', interpretation_avg:'DC fill in monitor range — aim for >97% to stay compliant', interpretation_strong:'Strong DC fill rate — supply chain meeting Walmart replenishment needs', interpretation_action_weak:'Check inventory availability at DC, case quantity accuracy, and inbound carrier on-time delivery.', walmart_threshold:97.0, walmart_threshold_note:'Below 97% triggers Walmart supply chain monitoring. Below 93% is a critical failure requiring immediate buyer communication.' },

  // ACV Distribution
  { brand_name:null, category:'All',    metric_name:'acv',  tier_weak:50.0, tier_avg_low:70.0, tier_avg_high:85.0, tier_strong:85.0, tier_elite:95.0, unit:'%', interpretation_weak:'Limited distribution — below 50% ACV means this item is only in a fraction of Walmart\'s volume. Significant distribution opportunity exists.', interpretation_avg:'Building distribution — 70-85% ACV is a growth phase; focus on gaining remaining high-ACV stores', interpretation_strong:'National distribution — strong ACV coverage across Walmart\'s volume base', interpretation_action_weak:'Identify which high-ACV Walmart stores do not carry this item. Build a distribution sell-in with velocity data from existing stores as proof.', walmart_threshold:null, walmart_threshold_note:null },

  // YoY Revenue Growth
  { brand_name:null, category:'All',    metric_name:'yoy_growth', tier_weak:0.0, tier_avg_low:0.0, tier_avg_high:8.0, tier_strong:8.0, tier_elite:20.0, unit:'%', interpretation_weak:'Revenue declining YoY — negative growth at Walmart is a significant buyer concern. Category growth typically runs 3-5%; declining means you are losing share.', interpretation_avg:'Modest growth — tracking with category average of 3-8%; maintaining share position', interpretation_strong:'Above-market growth — gaining share. Buyer will view this favorably in line review.', interpretation_action_weak:'Diagnose root cause: is it distribution loss, velocity decline, or price elasticity? Build a recovery narrative before the next buyer meeting.', walmart_threshold:null, walmart_threshold_note:null },
];

const insertBench = db.prepare(`INSERT INTO benchmark_reference (brand_name,category,metric_name,tier_weak,tier_avg_low,tier_avg_high,tier_strong,tier_elite,unit,interpretation_weak,interpretation_avg,interpretation_strong,interpretation_action_weak,walmart_threshold,walmart_threshold_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`);
for (const b of benchmarks) {
  insertBench.run(b.brand_name,b.category,b.metric_name,b.tier_weak,b.tier_avg_low,b.tier_avg_high,b.tier_strong,b.tier_elite,b.unit,b.interpretation_weak,b.interpretation_avg,b.interpretation_strong,b.interpretation_action_weak,b.walmart_threshold,b.walmart_threshold_note);
}
console.log(`  ✅ ${benchmarks.length} benchmark reference rows`);

// ─── Supply Chain Weekly Data ─────────────────────────────────────────────────
console.log('\nGenerating supply chain data...');
{
  const scRows = [];
  const brands = Object.keys(BRANDS);
  for (const week of WEEKS) {
    for (const brand of brands) {
      // Base OTIF around 97% with brand variation and occasional dips
      const baseOtif = brand === 'Bolt' ? 97.2 : brand === 'Apex' ? 97.8 : 96.5;
      const onTime  = Math.min(100, Math.max(85, randGaussClamp(baseOtif + 0.5, 1.2, 88, 100)));
      const inFull  = Math.min(100, Math.max(85, randGaussClamp(baseOtif - 0.5, 1.5, 85, 100)));
      const otif    = (onTime / 100) * (inFull / 100) * 100;
      const dcFill  = Math.min(100, Math.max(85, randGaussClamp(97.0, 1.8, 85, 100)));
      const caseFill = Math.min(100, Math.max(85, randGaussClamp(97.5, 1.2, 87, 100)));
      // Chargebacks only when OTIF < 95
      const chargebacks = otif < 95 ? +(randGaussClamp(8000, 4000, 1000, 35000)).toFixed(2) : 0;
      const compliance  = Math.min(100, Math.max(70, randGaussClamp(94, 4, 70, 100)));
      scRows.push([
        String(week), 'Walmart', String(brand),
        +otif.toFixed(2), +dcFill.toFixed(2), +caseFill.toFixed(2),
        +onTime.toFixed(2), +inFull.toFixed(2),
        +chargebacks.toFixed(2), +compliance.toFixed(1)
      ]);
    }
  }
  const insertSC = db.prepare(`INSERT INTO supply_chain_weekly (week_ending_date,retailer_name,brand_name,otif_rate_pct,dc_fill_rate_pct,case_fill_rate_pct,on_time_delivery_pct,in_full_delivery_pct,chargebacks_dollars,compliance_score) VALUES (?,?,?,?,?,?,?,?,?,?)`);
  const insertManySC = db.transaction(rows => { for (const r of rows) insertSC.run(...r); });
  insertManySC(scRows);
  console.log(`  ✅ ${scRows.length} supply chain rows (${WEEKS.length} weeks × ${brands.length} brands)`);
}

// ─── Metric Store Pre-computation ────────────────────────────────────────────
console.log('\nPre-computing metric store...');

const ANCHOR_DATE   = '2025-02-22';  // last Saturday in dataset
const PERIODS = [
  { label: 'L4W',  weeks: 4,   ytd: false },
  { label: 'L13W', weeks: 13,  ytd: false },
  { label: 'L52W', weeks: 52,  ytd: false },
  { label: 'YTD',  weeks: null, ytd: true  },
];

function periodDates(p) {
  if (p.ytd) {
    // YTD: Jan 1 of anchor year through anchor date
    const year = ANCHOR_DATE.slice(0, 4);
    return { start: `${year}-01-01`, end: ANCHOR_DATE };
  }
  // Last N weeks: go back p.weeks * 7 days from anchor
  const end = new Date(ANCHOR_DATE);
  const start = new Date(ANCHOR_DATE);
  start.setDate(start.getDate() - p.weeks * 7 + 1);
  return {
    start: start.toISOString().slice(0, 10),
    end:   end.toISOString().slice(0, 10),
  };
}

function priorYearDates(dates) {
  const s = new Date(dates.start); s.setFullYear(s.getFullYear() - 1);
  const e = new Date(dates.end);   e.setFullYear(e.getFullYear() - 1);
  return { start: s.toISOString().slice(0, 10), end: e.toISOString().slice(0, 10) };
}

const insertMetric = db.prepare(`
  INSERT OR REPLACE INTO metric_store (
    computed_at, period_label, period_start_date, period_end_date, num_weeks,
    grain, retailer_name, brand_name, sku_id, sku_description, region,
    revenue, units_sold, num_stores_selling, avg_selling_price,
    velocity_units_per_store_per_week,
    avg_acv_pct, distribution_points,
    avg_oos_rate_pct,
    revenue_prior_year, units_prior_year, velocity_prior_year,
    revenue_yoy_pct, velocity_yoy_pct,
    promo_events, avg_promo_lift_pct, avg_promo_roi, total_trade_spend,
    oos_above_threshold, velocity_trend
  ) VALUES (
    ?,?,?,?,?,  ?,?,?,?,?,?,
    ?,?,?,?,?,  ?,?,?,  ?,?,?,?,?,  ?,?,?,?,  ?,?
  )
`);

const now = new Date().toISOString();
let metricRows = 0;

for (const period of PERIODS) {
  const dates  = periodDates(period);
  const prior  = priorYearDates(dates);
  const numWeeks = period.ytd ? Math.round((new Date(dates.end) - new Date(dates.start)) / (7*86400000)) : period.weeks;

  // ── GRAIN: total ────────────────────────────────────────────────────────
  const totCur = db.prepare(`
    SELECT SUM(dollar_sales) rev, SUM(unit_sales) units,
           AVG(velocity_per_store) vel, AVG(avg_selling_price) price,
           AVG(num_stores_selling) stores, AVG(acv_distribution_pct) acv,
           AVG(num_stores_selling) dp, AVG(oos_rate_pct) oos
    FROM sales_kpi_weekly
    WHERE week_ending_date BETWEEN ? AND ? AND retailer_name='Walmart'
  `).get(dates.start, dates.end);

  const totPrior = db.prepare(`
    SELECT SUM(dollar_sales) rev, SUM(unit_sales) units, AVG(velocity_per_store) vel
    FROM sales_kpi_weekly
    WHERE week_ending_date BETWEEN ? AND ? AND retailer_name='Walmart'
  `).get(prior.start, prior.end);

  const promoTot = db.prepare(`
    SELECT COUNT(*) cnt, AVG(promo_lift_pct) lift, AVG(promo_roi) roi, SUM(trade_spend_dollars) spend
    FROM promo_calendar
    WHERE retailer_name='Walmart'
      AND promo_start_date BETWEEN ? AND ?
  `).get(dates.start, dates.end);

  const revYoy  = totPrior?.rev  ? +((totCur.rev  - totPrior.rev)  / totPrior.rev  * 100).toFixed(2) : null;
  const velYoy  = totPrior?.vel  ? +((totCur.vel  - totPrior.vel)  / totPrior.vel  * 100).toFixed(2) : null;

  insertMetric.run(
    now, period.label, dates.start, dates.end, numWeeks,
    'total', 'Walmart', null, null, null, null,
    +(totCur.rev||0).toFixed(2), +(totCur.units||0).toFixed(0),
    Math.round(totCur.stores||0), +(totCur.price||0).toFixed(2),
    +(totCur.vel||0).toFixed(3),
    +(totCur.acv||0).toFixed(2), Math.round(totCur.dp||0),
    +(totCur.oos||0).toFixed(2),
    +(totPrior?.rev||0).toFixed(2), +(totPrior?.units||0).toFixed(0),
    +(totPrior?.vel||0).toFixed(3),
    revYoy, velYoy,
    promoTot.cnt||0, promoTot.lift?+(promoTot.lift).toFixed(2):null,
    promoTot.roi?+(promoTot.roi).toFixed(3):null,
    promoTot.spend?+(promoTot.spend).toFixed(2):null,
    (totCur.oos||0) > 5 ? 1 : 0,
    velYoy === null ? 'flat' : velYoy > 2 ? 'up' : velYoy < -2 ? 'down' : 'flat'
  );
  metricRows++;

  // ── GRAIN: brand ────────────────────────────────────────────────────────
  const brands = db.prepare(`SELECT DISTINCT brand_name FROM sales_kpi_weekly WHERE retailer_name='Walmart'`).all();
  for (const { brand_name } of brands) {
    const bCur = db.prepare(`
      SELECT SUM(dollar_sales) rev, SUM(unit_sales) units,
             AVG(velocity_per_store) vel, AVG(avg_selling_price) price,
             AVG(num_stores_selling) stores, AVG(acv_distribution_pct) acv,
             AVG(num_stores_selling) dp, AVG(oos_rate_pct) oos
      FROM sales_kpi_weekly
      WHERE week_ending_date BETWEEN ? AND ?
        AND retailer_name='Walmart' AND brand_name=?
    `).get(dates.start, dates.end, brand_name);

    const bPrior = db.prepare(`
      SELECT SUM(dollar_sales) rev, SUM(unit_sales) units, AVG(velocity_per_store) vel
      FROM sales_kpi_weekly
      WHERE week_ending_date BETWEEN ? AND ?
        AND retailer_name='Walmart' AND brand_name=?
    `).get(prior.start, prior.end, brand_name);

    const bPromo = db.prepare(`
      SELECT COUNT(*) cnt, AVG(promo_lift_pct) lift, AVG(promo_roi) roi, SUM(trade_spend_dollars) spend
      FROM promo_calendar pc
      JOIN sales_kpi_weekly s ON pc.sku_id = s.sku_id
      WHERE pc.retailer_name='Walmart' AND s.brand_name=?
        AND pc.promo_start_date BETWEEN ? AND ?
    `).get(brand_name, dates.start, dates.end);

    const bRevYoy = bPrior?.rev ? +((bCur.rev - bPrior.rev) / bPrior.rev * 100).toFixed(2) : null;
    const bVelYoy = bPrior?.vel ? +((bCur.vel - bPrior.vel) / bPrior.vel * 100).toFixed(2) : null;

    insertMetric.run(
      now, period.label, dates.start, dates.end, numWeeks,
      'brand', 'Walmart', brand_name, null, null, null,
      +(bCur.rev||0).toFixed(2), +(bCur.units||0).toFixed(0),
      Math.round(bCur.stores||0), +(bCur.price||0).toFixed(2),
      +(bCur.vel||0).toFixed(3),
      +(bCur.acv||0).toFixed(2), Math.round(bCur.dp||0),
      +(bCur.oos||0).toFixed(2),
      +(bPrior?.rev||0).toFixed(2), +(bPrior?.units||0).toFixed(0),
      +(bPrior?.vel||0).toFixed(3),
      bRevYoy, bVelYoy,
      bPromo.cnt||0, bPromo.lift?+(bPromo.lift).toFixed(2):null,
      bPromo.roi?+(bPromo.roi).toFixed(3):null,
      bPromo.spend?+(bPromo.spend).toFixed(2):null,
      (bCur.oos||0) > 5 ? 1 : 0,
      bVelYoy === null ? 'flat' : bVelYoy > 2 ? 'up' : bVelYoy < -2 ? 'down' : 'flat'
    );
    metricRows++;
  }

  // ── GRAIN: sku ──────────────────────────────────────────────────────────
  const skus = db.prepare(`SELECT DISTINCT sku_id, sku_description FROM sales_kpi_weekly WHERE retailer_name='Walmart'`).all();
  for (const { sku_id, sku_description } of skus) {
    const brand_name = db.prepare(`SELECT DISTINCT brand_name FROM sales_kpi_weekly WHERE sku_id=? LIMIT 1`).get(sku_id)?.brand_name;
    const sCur = db.prepare(`
      SELECT SUM(dollar_sales) rev, SUM(unit_sales) units,
             AVG(velocity_per_store) vel, AVG(avg_selling_price) price,
             AVG(num_stores_selling) stores, AVG(acv_distribution_pct) acv,
             AVG(num_stores_selling) dp, AVG(oos_rate_pct) oos
      FROM sales_kpi_weekly
      WHERE week_ending_date BETWEEN ? AND ?
        AND retailer_name='Walmart' AND sku_id=?
    `).get(dates.start, dates.end, sku_id);

    const sPrior = db.prepare(`
      SELECT SUM(dollar_sales) rev, SUM(unit_sales) units, AVG(velocity_per_store) vel
      FROM sales_kpi_weekly
      WHERE week_ending_date BETWEEN ? AND ?
        AND retailer_name='Walmart' AND sku_id=?
    `).get(prior.start, prior.end, sku_id);

    const sPromo = db.prepare(`
      SELECT COUNT(*) cnt, AVG(promo_lift_pct) lift, AVG(promo_roi) roi, SUM(trade_spend_dollars) spend
      FROM promo_calendar
      WHERE retailer_name='Walmart' AND sku_id=?
        AND promo_start_date BETWEEN ? AND ?
    `).get(sku_id, dates.start, dates.end);

    const sRevYoy = sPrior?.rev ? +((sCur.rev - sPrior.rev) / sPrior.rev * 100).toFixed(2) : null;
    const sVelYoy = sPrior?.vel ? +((sCur.vel - sPrior.vel) / sPrior.vel * 100).toFixed(2) : null;

    insertMetric.run(
      now, period.label, dates.start, dates.end, numWeeks,
      'sku', 'Walmart', brand_name||null, sku_id, sku_description, null,
      +(sCur.rev||0).toFixed(2), +(sCur.units||0).toFixed(0),
      Math.round(sCur.stores||0), +(sCur.price||0).toFixed(2),
      +(sCur.vel||0).toFixed(3),
      +(sCur.acv||0).toFixed(2), Math.round(sCur.dp||0),
      +(sCur.oos||0).toFixed(2),
      +(sPrior?.rev||0).toFixed(2), +(sPrior?.units||0).toFixed(0),
      +(sPrior?.vel||0).toFixed(3),
      sRevYoy, sVelYoy,
      sPromo.cnt||0, sPromo.lift?+(sPromo.lift).toFixed(2):null,
      sPromo.roi?+(sPromo.roi).toFixed(3):null,
      sPromo.spend?+(sPromo.spend).toFixed(2):null,
      (sCur.oos||0) > 5 ? 1 : 0,
      sVelYoy === null ? 'flat' : sVelYoy > 2 ? 'up' : sVelYoy < -2 ? 'down' : 'flat'
    );
    metricRows++;
  }
}

console.log(`  ✅ ${metricRows} metric store rows pre-computed`);

console.log('\n=== Calibration check ===');
const velCheck = db.prepare(`
  SELECT brand_name,
    ROUND(MIN(velocity_per_store),2) as vel_min,
    ROUND(AVG(velocity_per_store),2) as vel_avg,
    ROUND(MAX(velocity_per_store),2) as vel_max,
    ROUND(MIN(avg_selling_price),2) as price_min,
    ROUND(AVG(avg_selling_price),2) as price_avg,
    ROUND(MAX(avg_selling_price),2) as price_max
  FROM sales_kpi_weekly WHERE retailer_name='Walmart'
  GROUP BY brand_name ORDER BY brand_name
`).all();
velCheck.forEach(r => console.log(r));

const roiCheck = db.prepare(`
  SELECT p.sku_id, s.brand_name,
    ROUND(MIN(p.promo_roi),2) as roi_min,
    ROUND(AVG(p.promo_roi),2) as roi_avg,
    ROUND(MAX(p.promo_roi),2) as roi_max,
    ROUND(AVG(p.promo_lift_pct),1) as avg_lift_pct
  FROM promo_calendar p
  JOIN (SELECT DISTINCT sku_id, brand_name FROM sales_kpi_weekly) s ON p.sku_id=s.sku_id
  WHERE p.retailer_name='Walmart'
  GROUP BY s.brand_name ORDER BY s.brand_name
`).all();
console.log('\n=== Promo ROI + Lift check (Walmart) ===');
roiCheck.forEach(r => console.log(r));

db.close();
console.log(`
✅ Generation complete — [SYNTHETIC DATA — DEMO ONLY]
   DB: ${DB_PATH}
`);

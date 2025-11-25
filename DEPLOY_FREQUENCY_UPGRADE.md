# 🚀 DEPLOY TRADING FREQUENCY UPGRADE

**Changes Made:**
- ✅ Lowered edge threshold: 5% → 3%
- ✅ Lowered confidence threshold: 70% → 60%
- ✅ Lowered weather model threshold: 8% → 4%
- ✅ Added weekly jobless claims parser (52 events/year!)
- ✅ Added jobless claims to news monitoring
- ✅ Added jobless claims consensus data

**Expected Result:** 15-30 trades/month (was 2-4/month)

---

## 📋 DEPLOYMENT STEPS

Run these commands on your server at `/root/Kalshi-Trading`:

### Step 1: Pull Latest Code

```bash
cd /root/Kalshi-Trading
git fetch origin
git checkout claude/study-kalshi-bot-01RffDvdbSQEA26qy18BAb2m
git pull origin claude/study-kalshi-bot-01RffDvdbSQEA26qy18BAb2m
```

### Step 2: Install scipy (for weather model)

```bash
# Add scipy to requirements.txt
echo "scipy>=1.11.0" >> requirements.txt
```

### Step 3: Rebuild Docker with New Code

```bash
# Stop current containers
docker-compose down

# Rebuild with no cache (ensures fresh install)
docker-compose build --no-cache

# Start containers
docker-compose up -d
```

### Step 4: Verify Deployment

```bash
# Check logs for new features
docker-compose logs --tail=100 app | grep -E "(min_edge|Weather model|JOBLESS_CLAIMS|consensus)"
```

You should see:
```
INFO: Speed arbitrage initialized: min_confidence=0.6, min_edge=0.03
INFO: Weather model initialized
INFO: JOBLESS_CLAIMS             230000 - Initial Jobless Claims...
```

### Step 5: Monitor Activity (First Hour)

```bash
# Watch for signals being generated
docker-compose logs -f app | grep -E "(SIGNAL|Generated signal|Weather|claims)"
```

You should see MORE activity than before:
- More economic signals (lower threshold catching medium-edge trades)
- Weather model scanning markets
- Jobless claims recognized when news hits (every Thursday 8:30am ET)

### Step 6: Check Paper Trades (First Week)

```bash
# See all paper trades
docker-compose logs app | grep PAPER | tail -30
```

Track:
- Total trades per day (should be 1-2/day vs 0-1/day before)
- Types of trades (economic, weather, claims)
- Win rate (should still be 60-70%+)
- P&L (should be positive after fees)

---

## 🎯 WHAT TO EXPECT

### **Week 1 Results (Expected):**

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Trades/week | 0-1 | 3-7 | 🚀 +500% |
| Signal types | Economic only | Economic + Weather + Claims | ✅ |
| Edge threshold | 5% | 3% | Lower = more trades |
| Confidence threshold | 70% | 60% | Lower = more trades |

### **Sample Week Activity:**

**Monday:**
- 2 weather signals (temperature markets)
- 0 trades executed (edges too small)

**Tuesday:**
- 1 weather trade: NYC temp market (4% edge) ✅

**Wednesday:**
- Economic data: Retail Sales +0.5% vs +0.3%
- 2 signals generated (lower threshold catches it now!)
- 2 trades executed ✅✅

**Thursday:**
- Jobless claims: 245k vs expected 235k
- 1 signal generated (10k surprise)
- 1 trade executed ✅

**Friday:**
- 3 weather signals (weekend forecasts)
- 2 trades executed ✅✅

**Total: 6 trades** (vs 1-2 trades before)

---

## ⚠️ IMPORTANT MONITORING

### First 3 Days:

Watch for:
1. ✅ **More signals generated** - Should see 2-3x as many
2. ✅ **Lower edge trades** - 3-4% edges executing (was 5%+ only)
3. ✅ **Weather model active** - Should see "Weather model" in logs
4. ✅ **Jobless claims recognized** - Next Thursday at 8:30am ET
5. ⚠️ **Win rate still good** - Should be 60-70%+ (slightly lower is OK)

### Red Flags (Stop if you see these):

❌ **Win rate <50%** - Too aggressive, revert to 5% threshold
❌ **Large consecutive losses** - Circuit breaker should trip, but watch
❌ **Weather model errors** - scipy might not be installed correctly
❌ **No increase in activity** - Code might not have deployed

---

## 🔄 ROLLBACK (If Needed)

If results are poor after 1 week, revert:

```bash
cd /root/Kalshi-Trading

# Edit config/config.yaml
# Change back to:
#   min_edge: 0.05
#   min_confidence: 0.70
#   weather_model min_edge: 0.08

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 📊 SUCCESS METRICS (After 2 Weeks)

You'll know it's working if:

| Metric | Target | How to Check |
|--------|--------|--------------|
| Trades/week | 5-10 | `docker-compose logs app \| grep PAPER \| wc -l` |
| Win rate | 60-70% | Count wins vs losses in logs |
| Avg edge | 3-6% | Look at signal logs |
| P&L trend | Positive | Sum up paper trade P&L |
| New trade types | Yes | Should see weather + claims trades |

**If all targets met:** Switch to LIVE trading with 50% position sizing!

**If targets not met:** Run in paper mode for another 2 weeks or revert.

---

## 📈 NEXT STEPS AFTER SUCCESS

Once paper trading proves profitable for 2-4 weeks:

1. **Week 3-4:** Continue monitoring paper trades
2. **Week 5:** Switch to LIVE with 50% sizing:
   - Edit `.env`: `PAPER_TRADING_MODE=false`
   - Lower position sizes in config (50% of current)
3. **Week 6-8:** Gradually scale up to 100% sizing
4. **Month 2+:** Full throttle, monitor monthly P&L

**Target:** $300-800/month by Month 2 📊

---

## 🆘 TROUBLESHOOTING

### "scipy not found" error:
```bash
docker-compose exec app pip install scipy
docker-compose restart app
```

### Weather model not active:
```bash
# Check logs
docker-compose logs app | grep -i weather | tail -20

# Should see: "Weather model initialized"
# If not, scipy isn't installed
```

### No jobless claims signals on Thursday:
- Make sure it's Thursday 8:30am ET when claims are released
- Check BossBot is posting claims data
- Check logs: `docker-compose logs app | grep -i "claims\|jobless"`

### Still only 1-2 trades/week:
- Verify config deployed: `docker-compose exec app cat /app/config/config.yaml | grep min_edge`
- Should show `0.03` not `0.05`
- If wrong, rebuild: `docker-compose down && docker-compose build --no-cache && docker-compose up -d`

---

## ✅ READY TO DEPLOY?

Follow steps 1-6 above and you'll be running the upgraded system in ~10 minutes!

**Paper trading is still active** so there's ZERO RISK. Watch for 1-2 weeks before going live.

# Air Quality Algorithm - Hybrid Approach

## 🎯 Overview

The BME680 Monitor uses a **hybrid algorithm** that combines:
1. **Absolute values** - Scientific thresholds based on gas resistance
2. **Relative values** - Comparison with calibrated baseline

This approach solves the critical problem of **contaminated baseline calibration**.

---

## ❌ Problem with Pure Relative Algorithm

### The Issue

The original algorithm used **only ratios** compared to baseline:

```python
ratio = current_gas / baseline

Good:     ratio > 1.35
Moderate: 0.70 ≤ ratio ≤ 1.35
Poor:     ratio < 0.70
```

### Why This Fails

**Scenario**: You calibrate in a room with bad air (e.g., after cooking)

- Baseline (contaminated): 30,000 Ω (30 kΩ)
- Current reading: 40,000 Ω (40 kΩ)
- Ratio: 1.33 → **"Moderate"**

**Problem**: 40 kΩ is objectively poor air quality, but the system thinks it's moderate because it's comparing to an even worse baseline!

---

## ✅ Hybrid Algorithm Solution

### How It Works

The system now performs **two independent assessments**:

#### 1️⃣ Absolute Assessment
Based on scientific BME680 research and empirical data:

```python
if gas_resistance > 150 kΩ:    # Excellent (outdoor clean air)
    return GOOD
elif gas_resistance > 100 kΩ:  # Good (well-ventilated indoor)
    return GOOD
elif gas_resistance > 50 kΩ:   # Moderate (typical indoor)
    return MODERATE
else:                           # < 50 kΩ (high VOCs)
    return POOR
```

#### 2️⃣ Relative Assessment
Detects changes from personal baseline:

```python
ratio = current_gas / baseline

if ratio > 1.35:    # Improved from baseline
    return GOOD
elif ratio < 0.70:  # Degraded from baseline
    return POOR
else:               # Similar to baseline
    return MODERATE
```

#### 3️⃣ Final Decision
**Use the worst case** for safety:

```python
final_quality = min(absolute_quality, relative_quality)
```

---

## 📊 Examples

### Example 1: Bad Baseline, Bad Air

**Situation**: Calibrated in contaminated room

- Baseline: 30 kΩ (bad)
- Current: 40 kΩ

**Old Algorithm (Pure Relative)**:
- Ratio: 1.33
- Result: **Moderate** ❌ (Wrong!)

**New Algorithm (Hybrid)**:
- Absolute: 40 kΩ → **Poor** (< 50 kΩ)
- Relative: 1.33 → Moderate
- Final: **Poor** ✅ (Correct!)

### Example 2: Good Baseline, Degraded Air

**Situation**: Calibrated in clean air, now cooking

- Baseline: 120 kΩ (good)
- Current: 60 kΩ

**Old Algorithm**:
- Ratio: 0.50
- Result: **Poor** ✅

**New Algorithm**:
- Absolute: 60 kΩ → Moderate
- Relative: 0.50 → **Poor**
- Final: **Poor** ✅

### Example 3: Good Baseline, Good Air

**Situation**: Calibrated and running in clean air

- Baseline: 120 kΩ
- Current: 150 kΩ

**Old Algorithm**:
- Ratio: 1.25
- Result: **Good** ✅

**New Algorithm**:
- Absolute: 150 kΩ → **Good**
- Relative: 1.25 → Moderate
- Final: **Good** ✅ (Actually even better!)

### Example 4: Bad Baseline, Very Good Air

**Situation**: Calibrated badly, moved to clean outdoor air

- Baseline: 30 kΩ (bad)
- Current: 180 kΩ (excellent!)

**Old Algorithm**:
- Ratio: 6.0
- Result: **Good** ✅ (but doesn't show how excellent it really is)

**New Algorithm**:
- Absolute: 180 kΩ → **Good** (excellent tier)
- Relative: 6.0 → **Good**
- Final: **Good** ✅

---

## 🔬 Scientific Basis

### BME680 Gas Resistance Ranges

Based on Bosch Sensortec documentation and empirical research:

| Resistance | Air Quality | Environment | VOC Level |
|------------|-------------|-------------|-----------|
| > 200 kΩ | Excellent | Outdoor, pristine | Very Low |
| 150-200 kΩ | Excellent | Outdoor, clean | Very Low |
| 100-150 kΩ | Good | Indoor, ventilated | Low |
| 50-100 kΩ | Moderate | Indoor, typical | Moderate |
| 30-50 kΩ | Poor | Indoor, stuffy | High |
| < 30 kΩ | Very Poor | Contaminated | Very High |

### Why Gas Resistance Indicates Air Quality

The BME680 contains a **metal oxide (SnO₂)** gas sensor:

1. **Clean Air** → Few VOCs → High resistance (> 100 kΩ)
2. **Polluted Air** → Many VOCs → Low resistance (< 50 kΩ)

VOCs (Volatile Organic Compounds) include:
- Cooking fumes
- Cleaning products
- Perfumes/deodorants
- Paint fumes
- Smoke
- CO₂ (indirectly)

---

## ⚙️ Configuration

All thresholds are configurable in `config/config.yaml`:

```yaml
air_quality:
  # Relative thresholds (baseline comparison)
  good_threshold: 1.35
  poor_threshold: 0.70

  # Absolute thresholds (scientific ranges)
  excellent_threshold: 150000  # 150 kΩ
  good_threshold_abs: 100000   # 100 kΩ
  moderate_threshold: 50000    # 50 kΩ

  # Baseline validation
  clean_air_min: 50000   # Warn if baseline < 50 kΩ
  clean_air_max: 200000  # Excellent if baseline > 200 kΩ
```

---

## 🎨 Customization

### Adjusting for Your Environment

#### More Sensitive (Stricter)
```yaml
excellent_threshold: 120000  # Require higher quality for "Good"
good_threshold_abs: 80000
moderate_threshold: 40000
```

#### Less Sensitive (Relaxed)
```yaml
excellent_threshold: 180000
good_threshold_abs: 120000
moderate_threshold: 60000
```

#### Only Relative (Original Behavior)
You can't disable absolute checking, but you can make it very permissive:

```yaml
moderate_threshold: 10000  # Almost everything passes absolute check
```

---

## 🧪 Testing

The hybrid algorithm is tested in `tests/test_air_quality.py`:

```python
def test_hybrid_algorithm_bad_baseline():
    """Test that bad baseline + bad air = Poor (not Good)."""
    calculator = AirQualityCalculator(
        moderate_threshold_abs=50000,
        ...
    )

    # Simulate bad baseline
    calculator.gas_baseline = 30000  # 30 kΩ (bad)

    # Test with slightly better air
    index, label = calculator.update(gas_resistance=40000, heat_stable=True)

    # Should be Poor due to absolute threshold, not Good from ratio
    assert index == AirQualityLevel.POOR
```

---

## 📈 Benefits

### 1. **Robustness**
- Works even with contaminated baseline
- Self-correcting through absolute thresholds

### 2. **Scientific Accuracy**
- Based on documented BME680 behavior
- Matches real-world VOC levels

### 3. **Sensitivity**
- Still detects relative changes
- Warns about degradation

### 4. **Safety First**
- Uses worst-case assessment
- Never under-reports poor air quality

---

## 🔄 Migration

### For Existing Users

The new algorithm is **backward compatible** but more conservative:

- **Old Good** might become **Moderate** if absolute value is borderline
- **Old Moderate** might become **Poor** if absolute value is low
- This is intentional and correct!

### Recalibration Recommended

For best results with the new algorithm:

1. Delete `gas_baseline.json`
2. Restart sensor in **clean outdoor air**
3. Wait for new calibration (10 minutes)
4. Baseline will now be accurate

---

## 📊 Algorithm Flow

```
┌─────────────────────┐
│ Read Gas Resistance │
└──────────┬──────────┘
           │
           ├─────────────────────┬────────────────────┐
           │                     │                    │
   ┌───────▼────────┐   ┌────────▼────────┐  ┌──────▼──────┐
   │ Absolute Check │   │ Relative Check  │  │  Baseline   │
   │ (Scientific)   │   │ (Personal)      │  │ Validation  │
   └───────┬────────┘   └────────┬────────┘  └──────┬──────┘
           │                     │                    │
           │      ┌──────────────┼────────────────────┘
           │      │              │
           │      │        ┌─────▼─────┐
           │      │        │  Warning  │
           │      │        │  if bad   │
           │      │        └───────────┘
           │      │
      ┌────▼──────▼────┐
      │  min(abs, rel) │  ← Use worst case
      └────────┬───────┘
               │
         ┌─────▼─────┐
         │   Result  │
         │ Good/Mod/ │
         │   Poor    │
         └───────────┘
```

---

## 🎓 Further Reading

- [Bosch BME680 Datasheet](https://www.bosch-sensortec.com/products/environmental-sensors/gas-sensors/bme680/)
- [Indoor Air Quality Standards](https://www.epa.gov/indoor-air-quality-iaq)
- [VOC Levels and Health](https://www.airnow.gov/aqi/aqi-basics/)

---

**Version**: 2.0.0 | **Last Updated**: 2024-12-27

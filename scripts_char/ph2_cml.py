import pprint

import matplotlib.pyplot as plt
import numpy as np
import scipy.interpolate as interp
import scipy.optimize as opt
import scipy.signal as sig

from bag.util.search import BinaryIterator
from bag.util.search import minimize_cost_golden_float
from bag.data.lti import LTICircuit
from bag.data.lti import get_w_3db
from bag.data.lti import get_stability_margins
from verification_ec.mos.query import MOSDBDiscrete

# Additional constraints
# Channel length of 90 nm:
# pmos_spec = 'specs_mos_char/pch_w0d5.yaml' ***
# nmos_spec = 'specs_mos_char/nch_w0d5_90n.yaml'
# LVT threshold flavor:
# intent = 'lvt'

def get_db(spec_file, intent, interp_method = 'spline', sim_env = 'tt'):
    # Initialize transistor database from simulation data
    mos_db = MOSDBDiscrete([spec_file], interp_method = interp_method)
    # Set process corners
    mos_db.env_list = [sim_env]
    # Set layout parameters
    mos_db.set_dsn_params(intent = intent)
    return mos_db


def design_cml_latch_comp(specs):
    sim_env = specs['sim_env']
    # pch_db = specs['pch_db']
    nch_db = specs['nch_db']
    vgs_res = specs['vgs_res']
    vdd = specs['vdd']
    tper = specs['tper']
    tr = specs['tr']
    tsu = specs['tsu']
    tclk = tper - tr - tsu
    vamp = specs['vamp']
    vin_off = specs['vin_off']
    cff = specs['cff']
    vmin = specs['vmin']
    cyield = specs['cyield']
    vin_cm = specs['vin_cm']
    vs = specs['vs']
    scale_min = specs['scale_min']
    scale_max = specs['scale_max']
    n_scale = specs['n_scale']
    vout_cm_min = specs['vout_cm_min']
    vout_cm_max = specs['vout_cm_max']
    n_vout_cm = specs['n_vout_cm']

    if cyield != 0:
      nsigma = np.sqrt(2) * scipy.erfinv(cyield)

    if cyield == 0:
      for scale in np.linspace(scale_min, scale_max, n_scale):
        # for vout_cm in np.linspace(vs, vdd, n_vout_cm):
        for vout_cm in np.linspace(vout_cm_min, vout_cm_max, n_vout_cm):
          nch_amp_info = nch_db.query(vgs=vin_cm-vs, vds=vout_cm-vs, vbs=-vs)
          vstar_amp = nch_amp_info['vstar']
          ib = nch_amp_info['ibias'] * scale
          gm_amp = nch_amp_info['gm'] * scale
          gds_amp = nch_amp_info['gds'] * scale
          ro_amp = 1 / gds_amp
          cgg_amp = nch_amp_info['cgg'] * scale
          cdd_amp = nch_amp_info['cdd'] * scale

          nch_regen_info = nch_db.query(vgs=vout_cm-vs, vds=vout_cm-vs, vbs=-vs)
          ib_regen = nch_regen_info['ibias'] * scale
          regen_scale = ib / ib_regen
          gm_regen = nch_regen_info['gm'] * regen_scale * scale
          gds_regen = nch_regen_info['gds'] * regen_scale * scale
          ro_regen = 1 / gds_regen
          cgg_regen = nch_regen_info['cgg'] * regen_scale * scale
          cdd_regen = nch_regen_info['cdd'] * regen_scale * scale

          rl = (vdd - vout_cm) / ib
          rout_amp = rl * ro_amp / (rl + ro_amp)
          av_amp = gm_amp * rout_amp
          cl = cff + cdd_amp + cgg_regen + cdd_regen
          wbw_amp = 1 / (rout_amp * cl)

          vod_hyst = ib * rl * np.exp(-tclk / 2 * wbw_amp)
          vod_new =  vamp * gm_amp * rout_amp * (1 - np.exp(-tclk / 2 * wbw_amp))
          vod_amp = vod_new - vod_hyst

          if vod_amp < 0: # Hysteresis check
            continue

          if ib * (tclk / 2) / cl < vod_new: # Slewing check
            continue

          rout_regen = rl * ro_regen / (rl + ro_regen)
          av_regen = gm_regen * rout_regen
          wbw_regen = 1 / (rout_regen * cl)

          vod_regen = np.exp(tclk / 2 * (av_regen - 1) * wbw_regen)
          vod = vod_amp * vod_regen
          if vod >= vmin:
            ibias = 2 * ib
            design = dict(
              IB = ibias,
              Scale = scale,
              Regen_Scale = regen_scale,
              Vod_Hyst = vod_hyst,
              Vod_New = vod_new,
              Vod = vod,
              RL = rl,
              CL = cl,
              Vout_CM = vout_cm,
              Av_Amp = av_amp,
              Av_Regen = av_regen,
              wbw_Amp = wbw_amp,
              wbw_Regen = wbw_regen,
              gm_Amp = gm_amp,
              gm_Regen = gm_regen,
              Vstar_Amp = vstar_amp
              )
            return design


def run_main():
    # pmos_spec = 'specs_mos_char/pch_w0d5.yaml'
    nmos_spec = 'specs_mos_char/nch_w0d5_90n.yaml'
    intent = 'lvt'
    sim_env = 'tt'
    interp_method = 'linear'

    # pch_db = get_db(pmos_spec, intent, interp_method = interp_method, sim_env = sim_env)
    nch_db = get_db(nmos_spec, intent, interp_method = interp_method, sim_env = sim_env)

    specs = dict(
        sim_env = sim_env,
        # pch_db = pch_db,
        nch_db = nch_db,
        vgs_res = 5e-3,
        vdd = 1.2,
        tper = 200e-12, # 200, 200, 300
        tr = 20e-12,
        tsu = 30e-12,
        vamp = 20e-3, # 20, 20, 5
        vin_off = 1.2, # 1.2 (unconstrained), 25e-3, 10e-3
        cff = 5e-15, # 5, 5, 2.5
        vmin = 200e-3,
        cyield = 0, # 0 (unconstrained), 0.9999, 0.9999
        vin_cm = 0.6,
        vs = 0.2,
        scale_min = 1,
        scale_max = 50,
        n_scale = 100,
        vout_cm_min = 0.6,
        vout_cm_max = 1.1,
        n_vout_cm = 100
        )

    comp_specs = design_cml_latch_comp(specs)
    pprint.pprint(comp_specs)


if __name__ == '__main__':
    run_main()
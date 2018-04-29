from collections import OrderedDict
import os
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

from bag import BagProject
from bag.io import load_sim_results, save_sim_results, load_sim_file

# Additional constraints
# Channel length of 90 nm:
# pmos_spec = 'specs_mos_char/pch_w0d5_90.yaml'
# nmos_spec = 'specs_mos_char/nch_w0d5_90.yaml'
# LVT threshold flavor:
# intent = 'lvt'

def get_db(spec_file, intent, interp_method='spline', sim_env='tt'):
    # Initialize transistor database from simulation data
    mos_db = MOSDBDiscrete([spec_file], interp_method=interp_method)
    # Set process corners
    mos_db.env_list = [sim_env]
    # Set layout parameters
    mos_db.set_dsn_params(intent=intent)
    return mos_db


def determine_op(specs):
    sim_env = specs['sim_env']
    # pch_db = specs['pch_db']
    nch_db = specs['nch_db']
    vdd = specs['vdd']
    vin_cm = specs['vin_cm']
    vout_cm = specs['vout_cm']
    vs = specs['vs']

    vgs = vin_cm - vs
    vds = vout_cm - vs

    nch_op = nch_db.query(vgs=vgs, vds=vds, vbs=-vs)

    return nch_op


def design_diff_amp(specs, nch_op):
    sim_env = specs['sim_env']
    # pch_db = specs['pch_db']
    nch_db = specs['nch_db']
    vdd = specs['vdd']
    vin_cm = specs['vin_cm']
    vout_cm = specs['vout_cm']
    vs = specs['vs']
    cl = specs['cl']
    tper = specs['tper']
    f3db_targ = 2 * 1/tper
    scale_min = specs['scale_min']
    scale_max = specs['scale_max']

    scale_iter = BinaryIterator(scale_min, scale_max, step = 1)
    while scale_iter.has_next():
        scale = scale_iter.get_next();

        ids = nch_op['ibias'] * scale
        gm = nch_op['gm'] * scale
        gds = nch_op['gds'] * scale
        ro = 1 / gds
        cdd = nch_op['cdd'] * scale

        rl = (vdd - vout_cm) / ids
        rout = rl * ro / (rl + ro)
        ctot = cl + cdd

        w3db = 1 / (rout * ctot)
        f3db = w3db / (2 * np.pi)

        design = OrderedDict(
            Scale = scale,
            IB = ids,
            RL = rl,
            f3dB = f3db
            )

        if f3db > f3db_targ:
            scale_iter.down()
        else:
            scale_iter.up()
        scale_iter.save_info(design)

    return scale_iter.get_last_save_info()



def run_main():
    # pmos_spec = 'specs_mos_char/pch_w0d5_90n.yaml'
    nmos_spec = 'specs_mos_char/nch_w0d5_90n.yaml'
    intent = 'lvt'
    interp_method = 'linear'
    sim_env = 'tt'

    # pch_db = get_db(pmos_spec, intent, interp_method=interp_method, sim_env=sim_env)
    nch_db = get_db(nmos_spec, intent, interp_method=interp_method, sim_env=sim_env)

    specs = dict(
        sim_env = sim_env,
        # pch_db = pch_db,
        nch_db = nch_db,
        vdd = 1.2,
        vin_cm = 0.7,
        vout_cm = 0.6,
        vs = 0.1,
        cl = 5e-15,
        tper = 120e-12,
        scale_min = 1,
        scale_max = 1000000
        )

    nch_op = determine_op(specs)
    diff_amp_specs = design_diff_amp(specs, nch_op)
    pprint.pprint(diff_amp_specs)


if __name__ == '__main__':
    run_main()

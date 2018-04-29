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

def get_db(spec_file, intent, interp_method = 'spline', sim_env = 'tt'):
    # Initialize transistor database from simulation data
    mos_db = MOSDBDiscrete([spec_file], interp_method = interp_method)
    # Set process corners
    mos_db.env_list = [sim_env]
    # Set layout parameters
    mos_db.set_dsn_params(intent = intent)
    return mos_db


def get_gm(specs):
    nch_db = specs['nch_db']
    for vstar in [0.11, 0.12, 0.13, 0.15, 0.17, 0.2, 0.3, 0.4, 1]:
        vstar_like = 4 / vstar**2
        nch_info = nch_db.query(vstar=vstar, vds=0.4, vbs=0)
        vgs = nch_info['vgs']
        print(vstar_like)
        print(vgs)
    return

def run_main():
    nmos_spec = 'specs_mos_char/nch_w0d5_90n.yaml'
    intent = 'lvt'
    sim_env = 'tt'
    interp_method = 'linear'

    nch_db = get_db(nmos_spec, intent, interp_method = interp_method, sim_env = sim_env)

    specs = dict(
        nch_db = nch_db
        )

    get_gm(specs)

if __name__ == '__main__':
    run_main()
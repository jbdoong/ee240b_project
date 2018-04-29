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
# Channel length of 45 nm:
# pmos_spec = 'specs_mos_char/pch_w0d5.yaml'
# nmos_spec = 'specs_mos_char/nch_w0d5.yaml'
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
    """
    Find operating point given VDD. Assume DC Vout (and Vin) to be VDD/2.
    """
    sim_env = specs['sim_env']
    pch_db = specs['pch_db']
    nch_db = specs['nch_db']
    vdd = specs['vdd']

    vgsn = vdd/2
    vgsp = -(vdd - vgsn)
    vdsn = vdd/2
    vdsp = -(vdd - vdsn)

    pch_op_info = pch_db.query(vgs=vgsp, vds=vdsp, vbs=0)
    nch_op_info = nch_db.query(vgs=vgsn, vds=vdsn, vbs=0)
    pch_ibias = pch_op_info['ibias']
    nch_ibias = nch_op_info['ibias']
    pch_scale = nch_ibias / pch_ibias

    return pch_op_info, nch_op_info, pch_scale


def design_inv_tia(specs, pch_op_info, nch_op_info, pch_scale):
    sim_env = specs['sim_env']
    pch_db = specs['pch_db']
    nch_db = specs['nch_db']
    vgs_res = specs['vgs_res']
    vdd = specs['vdd']
    isw = specs['isw']
    ber_targ = specs['ber']
    voff = specs['voff']
    snr_like_targ = specs['snr_like']
    pmos_noise_scale = specs['pmos_noise_scale']
    # rdc_targ = specs['rdc']
    noise_const = specs['noise_const']
    tper = specs['tper']
    f_factor = specs['f_factor']
    # f3db_targ = specs['f3db']
    f3db_targ = f_factor * 1 / tper
    pm_targ = specs['pm']
    cin = specs['cin']
    cl = specs['cl']
    scale_min = specs['scale_min']
    scale_max = specs['scale_max']
    n_scale = specs['n_scale']
    rf_min = specs['rf_min']
    rf_max = specs['rf_max']
    n_rf = specs['n_rf']

    pch_ibias = pch_op_info['ibias']
    nch_ibias = nch_op_info['ibias']

    gmp = pch_op_info['gm'] * pch_scale
    gmn = nch_op_info['gm']
    gm_tot = gmp + gmn
    gammap = pch_op_info['gamma']
    gamman = nch_op_info['gamma']
    gdsp = pch_op_info['gds'] * pch_scale
    gdsn = nch_op_info['gds']
    rop = 1 / gdsp
    ron = 1 / gdsn
    ro_tot = rop * ron / (rop + ron)
    gds_tot = 1 / ro_tot

    cgsp = pch_op_info['cgs'] * pch_scale
    cgsn = nch_op_info['cgs']
    cgs_tot = cgsp + cgsn
    cgbp = pch_op_info['cgb'] * pch_scale
    cgbn = nch_op_info['cgb']
    cgb_tot = cgbp + cgbn
    cgdp = pch_op_info['cgd'] * pch_scale
    cgdn = nch_op_info['cgd']
    cgd_tot = cgdp + cgdn
    cggp = pch_op_info['cgg'] * pch_scale
    cggn = nch_op_info['cgg']
    cgg_tot = cggp + cggn
    cdsp = pch_op_info['cds'] * pch_scale
    cdsn = nch_op_info['cds']
    cds_tot = cdsp + cdsn
    cdbp = pch_op_info['cdb'] * pch_scale
    cdbn = nch_op_info['cdb']
    cdb_tot = cdbp + cdbn
    cddp = pch_op_info['cdd'] * pch_scale
    cddn = nch_op_info['cdd']
    cdd_tot = cddp + cddn

    scale_vec = np.linspace(scale_min, scale_max, n_scale)
    for scale in scale_vec:
        for rf in np.linspace(rf_max, rf_min, n_rf):
            # Build circuit
            cir = LTICircuit()
            cir.add_transistor(pch_op_info, 'out', 'in', 'gnd', 'gnd', fg=scale*pch_scale)
            cir.add_transistor(nch_op_info, 'out', 'in', 'gnd', 'gnd', fg=scale)
            cir.add_res(rf, 'out', 'in')
            cir.add_cap(cin, 'in', 'gnd')
            cir.add_cap(cl, 'out', 'gnd')

            # Get gain/poles/zeros/Bode plot
            # Note: any in_type other than 'v' results in current source input
            tf = cir.get_transfer_function('in', 'out', in_type='i')
            rdc = np.absolute(tf.num[-1] / tf.den[-1])
            w3db = get_w_3db(tf.num, tf.den)
            f3db = w3db / (2 * np.pi)

            if f3db >= f3db_targ:
                # Noise
                in_gmp = noise_const * gammap * gmp
                in_gmn = noise_const * gamman * gmn
                in_rf = noise_const / rf

                tf_gm = cir.get_transfer_function('out', 'out', in_type='i')

                dc_gm = tf_gm.num[-1] / tf_gm.den[-1]
                wo2_gm = tf_gm.den[-1] / tf_gm.den[0]
                woQ_gm = tf_gm.den[-1] / tf_gm.den[1]
                wz_gm = tf_gm.num[-1] / tf_gm.num[0]
                von_gmp = pmos_noise_scale * in_gmp * dc_gm**2 * woQ_gm / 4 * (wo2_gm / wz_gm**2 + 1)
                von_gmn = in_gmn * dc_gm**2 * woQ_gm / 4 * (wo2_gm / wz_gm**2 + 1)

                cir.add_vccs(1, 'out', 'in', 'vn', 'gnd')
                tf_rf = cir.get_transfer_function('vn', 'out', in_type='v')

                dc_rf = tf_rf.num[-1] / tf_rf.den[-1]
                wo2_rf = tf_rf.den[-1] / tf_rf.den[0]
                woQ_rf = tf_rf.den[-1] / tf_rf.den[1]
                wz_rf = tf_rf.num[-1] / tf_rf.num[0]
                von_rf = in_rf * dc_rf**2 * woQ_rf / 4 * (wo2_rf / wz_rf**2 + 1)

                von = von_gmp + von_gmn + von_rf

                # Signal
                vo = isw * rdc
                snr_like = (vo - voff) / np.sqrt(von)

                if snr_like >= snr_like_targ:
                    cin_tot = cin + cgg_tot * scale
                    cl_tot = cl + cdd_tot * scale
                    cgd_scaled = cgd_tot * scale
                    gm_scaled = gm_tot * scale
                    gds_scaled = gds_tot * scale

                    # Build open loop circuit for phase margin
                    cir_open_loop = LTICircuit()
                    cir_open_loop.add_vccs(gm_scaled, 'out', 'gnd', 'vt', 'gnd') # ***
                    cir_open_loop.add_conductance(gds_scaled, 'out', 'gnd')
                    cir_open_loop.add_cap(cl_tot, 'out', 'gnd')
                    cir_open_loop.add_res(rf, 'out', 'vr')
                    cir_open_loop.add_cap(cgd_scaled, 'out', 'vr')
                    cir_open_loop.add_cap(cin_tot, 'vr', 'gnd')

                    tf_open_loop = cir_open_loop.get_transfer_function('vt', 'vr', in_type='v')
                    pm, gm = get_stability_margins(tf_open_loop.num, tf_open_loop.den)
                    pm = pm - 180

                    if pm >= pm_targ:
                        ibias = scale * nch_ibias
                        design = dict(
                            IB=ibias,
                            Scale=scale,
                            Rf=rf,
                            RDC=rdc,
                            f3dB=f3db,
                            PM=pm,
                            Von_Rf=von_rf,
                            Von_gmp=von_gmp,
                            Von_gmn=von_gmn,
                            Von=von,
                            SNR_Like=snr_like
                            )
                        return design


def run_main():
    pmos_spec = 'specs_mos_char/pch_w0d5.yaml'
    nmos_spec = 'specs_mos_char/nch_w0d5.yaml'
    intent = 'lvt'
    interp_method = 'linear'
    sim_env = 'tt'

    pch_db = get_db(pmos_spec, intent, interp_method=interp_method, sim_env=sim_env)
    nch_db = get_db(nmos_spec, intent, interp_method=interp_method, sim_env=sim_env)

    specs = dict(
        sim_env=sim_env,
        pch_db=pch_db,
        nch_db=nch_db,
        vgs_res=5e-3,
        vdd=1.2,
        isw=20e-6, # 10e-6, 20e-6
        ber=1e-12,
        voff=20e-3,
        snr_like=7, # 7, 7.5
        pmos_noise_scale=1, # 1, 6
        # rdc=8e3,
        noise_const=1.65e-20, # W/Hz
        tper=200e-12,
        f_factor=2/3, # 1/2, 2/3
        # f3db=4e9,
        pm=45,
        cin=100e-15, # 20, 100
        cl=40e-15,
        scale_min=1, # 1
        scale_max=10, # 2.5
        n_scale=100,
        rf_min=1e3, # 1e3
        rf_max=10e3, # 10e3
        n_rf=100
        )

    pch_op, nch_op, pch_scale = determine_op(specs)
    pprint.pprint(pch_scale)
    inv_tia_specs = design_inv_tia(specs, pch_op, nch_op, pch_scale)
    pprint.pprint(inv_tia_specs)


if __name__ == '__main__':
    run_main()

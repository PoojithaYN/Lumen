cd ~/planck
python << 'EOF'
import camb
import numpy as np
print("Testing if grey body affects C_l at FIXED H0:")
# Fixed H0 (not using cosmomc_theta)
p1 = camb.set_params(H0=67, ombh2=0.022, omch2=0.12, tau=0.06, As=2e-9, ns=0.96, lmax=2500, use_grey_body_radiation=0)
r1 = camb.get_results(p1)
cl1 = r1.get_cmb_power_spectra()['total']
p2 = camb.set_params(H0=67, ombh2=0.022, omch2=0.12, tau=0.06, As=2e-9, ns=0.96, lmax=2500,
                     custom_emissivity=0.9, transition_redshift=17, use_grey_body_radiation=1)
r2 = camb.get_results(p2)
cl2 = r2.get_cmb_power_spectra()['total']
# Check TT spectrum at l=100
diff_percent = abs(cl1[100,0] - cl2[100,0]) / cl1[100,0] * 100
print(f"Standard C_l(100): {cl1[100,0]:.6e}")
print(f"Grey body C_l(100): {cl2[100,0]:.6e}")
print(f"Difference: {diff_percent:.3f}%")
if diff_percent > 0.1:
    print("\n✓ Grey body IS affecting the physics (C_l changed)")
    print("Issue: cosmomc_theta solver might not be seeing the change")
else:
    print("\n❌ Grey body NOT affecting physics at all")
EOF
 
can you check if this python code can be convereted into lumen?

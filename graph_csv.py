import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
from matplotlib.pyplot import figure
import matplotlib
log_dir = "logs/"
csv = "wandb_export.csv"
df = pd.read_csv(csv)
log_names = os.listdir(log_dir)
matplotlib.rcParams.update({'font.size': 40})
matplotlib.rcParams.update({'axes.linewidth': 2.0})

prefixes = {
    #"Offline-DAgger SAC": "pretrained_sac_nosmirl_1000dagger_redo",
    #"Pretrained SAC (w/ planning) (2 Stage DAgger)": "pretrained_sac_nosmirl_1000dagger_2stage",
    "Offline-Online SAC": "pretrained_sac_nosmirl_nodagger{400}_ckpt",#"pretrained_sac_nosmirl_nodagger_redo",
    #"Pretrained (SMiRL) SAC (w/ planning) (2 Stage DAgger)": "pretrained_sac_smirl_1000dagger_2stage",
    #"Pretrained (SMiRL) SAC (w/ planning)": "pretrained_sac_smirl_1000dagger_redo",
    #"Pretrained (SMiRL) SAC (no planning)": "pretrained_sac_smirl_nodagger_redo",
    #"2 Stage DAgger SAC": "vanilla_sac_1000dagger_2stage",
    #"DAgger SAC": "vanilla_sac_1000dagger",
    "Vanilla SAC": "vanilla_sac_nodagger",
    #"SMiRL SAC (w/ planning) (2 Stage DAgger)": "smirl_sac_1000dagger_2stage",
    #"SMiRL SAC (w/ planning)": "smirl_sac_1000dagger",
    #"SMiRL SAC (no planning)": "smirl_sac_nodagger",
}
# for ckpt in [50, 100, 200, 400, 600]:
#     prefixes["Checkpoint {}".format(ckpt)] = "pretrained_sac_nosmirl_nodagger{" + str(ckpt) + "}_ckpt"
initial = {
    #"Offline-Online SAC": "pretrained_sac_nosmirl_nodagger_redo_initial",
    #"Vanilla SAC": "vanilla_sac_nodagger_initial"
}
graphs = { exp_name: 
    [os.path.join(log_dir, log_name, "progress.csv") for log_name in log_names if log_name[:len(prefix)] == prefix and log_name[len(prefix)].isdigit() ] 
    for exp_name, prefix in prefixes.items()
}
initial_graphs = { exp_name: 
    [os.path.join(log_dir, log_name, "progress.csv") for log_name in log_names if log_name[:len(prefix)] == prefix and log_name[len(prefix)].isdigit() ] 
    for exp_name, prefix in initial.items()
}
# graphs = {
#     "Pretrained SAC (no planning)": "logs/pretrained_sac_nodagger_2021-06-22 02:34:09.373771/progress.csv",
#     "Pretrained SAC (planning)": "logs/pretrained_sac_dagger_2021-06-16 22:58:27.262384/progress.csv",
#     "Vanilla SAC (planning)": "logs/vanilla_sac_dagger_2021-06-22 00:15:51.410218/progress.csv",
#     "Vanilla SAC (no planning)": "logs/vanilla_sac_nodagger_2021-06-24 04:57:19.839638/progress.csv",
#     "Pretrained (SMiRL) SAC (planning)": "logs/pretrainedsmirl_sac_dagger_2021-06-24 06:38:59.830893/progress.csv",
#     "Pretrained (SMiRL) SAC (no planning)": "logs/pretrainedsmirl_sac_nodagger_2021-06-24 07:42:36.141628/progress.csv"
# }
x_cap = 8000
min_diff = 50

def moving_average(x, w):
    return np.convolve(x, np.ones(w), 'valid') / w

def read_csvs(i, path):
    df = pd.read_csv(path)
    energy_cost = df["custom_metrics/energy_cost_mean"]
    if "custom_metrics/real_step_max" not in df.keys() or df["custom_metrics/real_step_max"].isnull().values.any():
        steps = df["info/num_steps_sampled"]
    else:
        steps = df["custom_metrics/real_step_max"]

    idx = steps < x_cap
    energy_cost = energy_cost[idx]
    steps = steps[idx]
    idx = [True]
    last_step = steps[0]
    for step in steps[1:]:
        if (step - last_step) > min_diff:
            idx.append(True)
            last_step = step
        else:
            idx.append(False)
    #idx = [True] + ((steps[1:] - steps[:-1]) > min_diff)
    steps = steps[idx]
    energy_cost = energy_cost[idx].to_numpy()
    print(energy_cost.min())
    if len(energy_cost) > 3:
        energy_cost[1:-1] = moving_average(energy_cost, 3)
    #steps = steps[1:-1]
    return energy_cost, steps



def plot_graph(ax, label, paths):
    if label in initial:
        initial_energy_costs = [[] for _ in range(5)]
        initial_paths = initial_graphs[label]
        for i, path in enumerate(initial_paths):
            energy_cost, initial_steps = read_csvs(i, path)
            initial_energy_costs[i] = (energy_cost + 40) * 250
        
    energy_costs = [[] for _ in range(5)]
    for i, path in enumerate(paths):
        energy_cost, steps = read_csvs(i, path)
        
        energy_costs[i] = (energy_cost + 40) * 250
    
    energy_costs = np.array(energy_costs)

    if label in initial:
        energy_costs = np.concatenate([initial_energy_costs, energy_costs],axis=-1)
        steps = np.concatenate([initial_steps, steps])

    if "DAgger" in label and "2 Stage DAgger" not in label:
        steps += 1000 # shift by 1000 steps to account for training time
        energy_costs = np.concatenate((np.array([(75+40)*250 for _ in range(5)]).reshape(5, -1), energy_costs), axis=1)
        steps = np.concatenate((np.array([999]), steps))
        # redo the x capping to account for shift
        idx = steps < x_cap
        energy_costs = energy_costs[:, idx]
        steps = steps[idx]
    means = energy_costs.mean(axis=0)
    ste = energy_costs.std(axis=0)/np.sqrt(5)
    ax.plot(steps, means,  label=label, linewidth=3.0)
    ax.fill_between(steps, means - ste, means + ste, alpha=0.2)
    return steps
    #ax.plot(steps, energy_costs, label=label)
def is_energy_cost(name):
    return "energy_cost_mean" in name and "MIN" not in name and "MAX" not in name

def plot_graph(ax, df):
    names = df.columns.values
    grp1 = []
    
    grp2 = []
    grp2_arr = []
    for name in names:
        if is_energy_cost(name) and "sac_ckpts" not in name:
            grp2.append(name)
            temp_df = df[["ray/tune/info/num_steps_sampled", name]]
            temp_df = temp_df.dropna()
            steps2 = df["ray/tune/info/num_steps_sampled"]
            grp2_arr.append(temp_df[name].to_numpy())
    grp2.append("ray/tune/info/num_steps_sampled")
    bigdf = df[grp2]
    bigdf = bigdf.dropna()
    steps2 = bigdf["ray/tune/info/num_steps_sampled"].to_numpy()
    grp2_arr = bigdf.drop("ray/tune/info/num_steps_sampled", axis=1).to_numpy()
    print(steps2.shape, grp2_arr.shape)
    df1 = df[["ray/tune/info/num_steps_sampled", "checkpoint: rl_algos/sac_ckpts/dashing-puddle-1030700.ckpt - ray/tune/custom_metrics/energy_cost_mean", "checkpoint: rl_algos/sac_ckpts/dashing-puddle-1030700.ckpt - ray/tune/custom_metrics/energy_cost_mean__MAX"]]
    df1 = df1.dropna()
    means1 = df1["checkpoint: rl_algos/sac_ckpts/dashing-puddle-1030700.ckpt - ray/tune/custom_metrics/energy_cost_mean"]
    ste1 = (df1["checkpoint: rl_algos/sac_ckpts/dashing-puddle-1030700.ckpt - ray/tune/custom_metrics/energy_cost_mean__MAX"] - means1)*250
    ste1 = ste1.to_numpy()
    means1 = 250*(means1.to_numpy() + 40)
    means2 = (grp2_arr.mean(axis=1)+40) * 250
    ste2 = (grp2_arr.std(axis=1)/np.sqrt(5)) * 250
    steps = df1["ray/tune/info/num_steps_sampled"]
    idx = steps < x_cap
    idx2 = steps2 < x_cap
    means1 = means1[idx]
    ste1 = ste1[idx]
    means2 = means2[idx2]
    ste2 = ste2[idx2]
    steps = steps[idx]
    steps2 = steps2[idx2]
    
    ax.plot(steps, means1,  label="Offline-Online SAC", linewidth=3.0)
    ax.fill_between(steps, means1 - ste1, means1 + ste1, alpha=0.2)
    ax.plot(steps2, means2,  label="Vanilla SAC", linewidth=3.0)
    ax.fill_between(steps2, means2 - ste2, means2 + ste2, alpha=0.2)
def plot_baselines(ax, steps):
    ax.plot(steps, np.array([(75 + 40) * 250 for step in steps]), label="TOU", linewidth=3.0)
    ax.plot(steps, np.array([(120) * 250 for step in steps]), label="Flat", linewidth=3.0)
fig, ax = plt.subplots(figsize=(30, 20))
plot_graph(ax, df)
# for label, paths in graphs.items():
#     steps = plot_graph(ax, label, paths)

plot_baselines(ax, list(range(x_cap)))
ax.spines['right'].set_visible(False)

ax.spines['top'].set_visible(False)
ax.set_ylabel("Average Annual Cost")
ax.set_xlabel("Number of Days/Steps Sampled")
ax.set_title("Effect of Pretraining")
ax.legend()
#ax.legend(loc='center', bbox_to_anchor=(0.75, 0.5))
plt.savefig("fig.png")
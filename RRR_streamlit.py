# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# IMPORT
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st
import re

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# PARAMS
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

class Params:

    columns_with_disturbance = ["Disturbance: Abbau Lieferant",
                                "Disturbance: PULSE Ausfall"
                                "Disturbance: STEP Ausfall Eigene Kapazität"
                                "Disturbance: STEP Ausfall externe Kapazität"
                                "Disturbance: STEP Nachfrage"
                                "Disturbance: PULSE Nachfrage"
                                "Disturbance: Preis Konkurrent 1"
                                "Disturbance: SWITCH Make to order vs Make to stock"]

    columns_with_kpis = ["KPI: Kapazitätsauslastung",
                         "KPI: Lieferfähigkeit",
                         "KPI: Kostenanteil an Umsatz"]

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# HELPER FUNCTIONS
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

def get_number_of_runs(df):

    # list to store the numbers of the runs
    runs = list()
    # loop through all column names
    for column_name in df.columns:
        # find this pattern in the column name
        match = re.search(r"Run (\d+):", column_name)
        # if a match was found...
        if match:
            # convert to integer number
            number = int(match.group(1))
            # append to list of run numbers
            runs.append(number)
    # remove duplicates
    runs = list(set(runs))

    return runs

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def create_df_for_runs(runs,df):

    # initialize dict to hold the dfs for all the runs
    dfs = dict()

    # loop through all runs
    for run in runs:
        # get all column names relevant for this run
        columns_for_run = [column for column in df.columns if f"Run {run}" in column]
        # add the "Time" column name
        columns_for_run.insert(0, "Time")
        # create subset of df for this run and store it in dict
        dfs[run] = df[columns_for_run]

    return dfs

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def get_params(key,df):

    params = dict()

    all_columns_without_disturbances = [name for name in df.columns if "disturbance" not in name.lower()]
    all_columns_without_disturbances_and_kpis = [name for name in all_columns_without_disturbances if "kpi" not in name.lower()]
    all_columns_without_disturbances_and_kpis.remove("Time")
    all_columns_without_disturbances_and_kpis.remove(f"Run {key}: Bewertung.Gesamtkosten")
    all_columns_without_disturbances_and_kpis.remove(f"Run {key}: Bewertung.Outbound transport costs transport costs")

    params_df = df[all_columns_without_disturbances_and_kpis]
    for column_name, column_data in params_df.items():
        min_value = column_data.min()
        max_value = column_data.max()
        if min_value != max_value:
            raise ValueError(f"Something is wrong with the parameter {column_name}. They are changing during the simulation")
        short_column_name = re.sub(rf"^Run {key}: ", "", column_name)
        params[short_column_name] = min_value

    return params

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def detect_column_with_disturbance(df):

    all_columns_with_disturbance = [name for name in df.columns if "disturbance" in name.lower()]

    columns_with_disturbance = list()
    for column in all_columns_with_disturbance:
        if df[column].nunique() != 1:
            columns_with_disturbance.append(column)

    if len(columns_with_disturbance) == 1:
        column_with_disturbance = columns_with_disturbance[0]
    elif len(columns_with_disturbance) > 1:
        # TODO: Ist es immer die Letzte?
        column_with_disturbance = columns_with_disturbance[-1]
    else:
        raise ValueError("No disturbance detected!")

    return column_with_disturbance

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def detect_disturbance(df,column_with_disturbance):

    # Get initial month
    initial_month = df.loc[0, 'Time']
    # Get initial value of disturbance-column
    initial_value = df.loc[df['Time'] == initial_month, column_with_disturbance].iloc[0]

    # Index and month of the first row where the value of the disturbance is greater than the initial value
    start_index = df.loc[df[column_with_disturbance] > initial_value].index[0]
    start_month = df['Time'].iloc[start_index]
    # Index and month of the last row where the value of the disturbance is greater than the initial value
    end_index = df.loc[df[column_with_disturbance] > initial_value].index[-1]
    end_month = df['Time'].iloc[end_index]

    # Get magnitude of disturbance
    # TODO: Is disturbance always an increase? (e.g. column "Nachfrage" -> decrease?)
    magnitude = df[column_with_disturbance].max()

    # IDEA GIAN... not needed so far...
    min_value = df[column_with_disturbance].min()
    max_value = df[column_with_disturbance].max()

    return start_index,start_month,end_index,end_month,magnitude

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def detect_effect(df,sheet_values,column_with_effect,threshold_lb,threshold_ub):

    initial_month = df.loc[0, 'Time']
    initial_value = df.loc[df['Time'] == initial_month, column_with_effect].iloc[0]

    # Index and month of first row after the disturbance start where the value of the effect is not equal the initial value
    start_index = df.loc[(df.index >= sheet_values["disturbance_start_index"]) & (df[column_with_effect] != initial_value)].index[0]
    start_month = df['Time'].iloc[start_index]

    # Index and month of last row after the disturbance end where the value of the effect is not inside the range to call the effect as over
    # TODO : GIAN : index of last row where effect not equal to initial value, or row where effect is back to initial value?
    end_index = df.loc[(df.index >= sheet_values["disturbance_end_index"]) & (df[column_with_effect] < threshold_lb) | (df[column_with_effect] > threshold_ub)].index[-1]
    end_month = df['Time'].iloc[end_index]

    # IDEA GIAN
    min_value = df.loc[(df.index >= start_index) & (df.index <= end_index),column_with_effect].min()
    max_value = df.loc[(df.index >= start_index) & (df.index <= end_index),column_with_effect].max()

    return start_index,start_month,end_index,end_month,initial_value,min_value,max_value

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def calculate_hardness(results):

    # Parameter
    # tc := time when the disturbance starts to affect the system
    # TODO: Start der Disturbance oder Start des Effekts?
    tc = results["disturbance_start_month"]
    # td := time when the disturbance stops
    td = results["disturbance_end_month"]
    # magnitude (delta) := magnitude of disturbance
    # TODO: Wie genau ist die "magnitude" zu messen?
    magnitude = results["disturbance_magnitude"]

    # ··················································································································

    # Calculate disturbance
    # disturbance (sigma) := disturbance affecting the syste
    # TODO: Gemäss Paper, sind disturbance und hardness m.E. dasselbe... (sigma und sigma_H)
    disturbance = magnitude * (td - tc)

    # ··················································································································

    # calculate otd_hardness
    otd_hardness = disturbance * (td - tc)

    # ··················································································································

    # calculate cost_hardness
    cost_hardness = disturbance * (td - tc)

    # ··················································································································

    # calculate capacity_hardness
    capacity_hardness = disturbance * (td - tc)

    # ··················································································································

    return otd_hardness,cost_hardness,capacity_hardness


# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def calculate_robustness(results):

    # Parameter
    # magnitude (sigma) := magnitude of disturbance
    magnitude = results["disturbance_magnitude"]

    # ··················································································································

    # calculate otd_robustness
    # A := ???
    # TODO: Definition fehlt
    A = results["otd_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["otd_effect_min_value"]
    otd_robustness = magnitude / (A - B)

    # ··················································································································

    # calculate cost_robustness
    # A := ???
    # TODO: Definition fehlt
    A = results["cost_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["cost_effect_min_value"]
    cost_robustness = magnitude / (A - B)

    # ··················································································································

    # calculate capacity_robustness
    # A := ???
    # TODO: Definition fehlt
    A = results["capacity_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["capacity_effect_min_value"]
    capacity_robustness = magnitude / (A - B)

    # ··················································································································

    return otd_robustness,cost_robustness,capacity_robustness

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def calculate_recover_rapidity(results):
    """recover rapidity := the average rate at which a system returns to equilibrium after a disturbance."""

    # Parameter
    # td := time when the disturbance stops
    td = results["disturbance_end_month"]

    # ··················································································································

    # calculate otd_recover_rapidity
    # tf := time when the system fully recovers
    tf = results["otd_effect_end_month"]
    # A := ???
    # TODO: Definition fehlt!
    A = results["otd_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt!
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["otd_effect_min_value"]
    otd_recover_rapidity = (A - B) / (tf - td)

    # ··················································································································

    # calculate cost_recover_rapidity
    # tf := time when the system fully recovers
    tf = results["cost_effect_end_month"]
    # A := ???
    # TODO: Definition fehlt!
    A = results["cost_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt!
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["cost_effect_min_value"]
    cost_recover_rapidity = (A - B) / (tf - td)

    # ··················································································································

    # calculate capacity_recover_rapidity
    # tf := time when the system fully recovers
    tf = results["capacity_effect_end_month"]
    # A := ???
    # TODO: Definition fehlt!
    A = results["capacity_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt!
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["capacity_effect_min_value"]
    capacity_recover_rapidity = (A - B) / (tf - td)

    # ··················································································································

    return otd_recover_rapidity, cost_recover_rapidity, capacity_recover_rapidity

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def calculate_normalized_kpis(kpis):

    min_value = kpis.min()
    max_value = kpis.max()

    n_kpis = kpis.apply(lambda x: (x - min_value) / (max_value - min_value))

    return n_kpis

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# FUNCTIONS
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

def read_csv(csv_file):

    df = pd.read_csv(csv_file)
    runs = get_number_of_runs(df)
    dfs = create_df_for_runs(runs,df)

    return dfs

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def extract_params(dfs):

    params = dict()

    for key,df in dfs.items():
        params[key] = get_params(key,df)

    return params

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def analyze_dfs(dfs):

    # results we want to extract
    column_names = ["disturbance_start_index", "disturbance_start_month", "disturbance_end_index",
                    "disturbance_end_month", "disturbance_magnitude",
                    "otd_effect_start_index", "otd_effect_start_month", "otd_effect_end_index", "otd_effect_end_month",
                    "otd_effect_initial_value", "otd_effect_min_value", "otd_effect_max_value",
                    "cost_effect_start_index", "cost_effect_start_month", "cost_effect_end_index",
                    "cost_effect_end_month", "cost_effect_initial_value", "cost_effect_min_value",
                    "cost_effect_max_value",
                    "capacity_effect_start_index", "capacity_effect_start_month", "capacity_effect_end_index",
                    "capacity_effect_end_month", "capacity_effect_initial_value", "capacity_effect_min_value",
                    "capacity_effect_max_value"]

    results = pd.DataFrame(columns=column_names)

    for key,df in dfs.items():

        sheet_values = dict()
        column_with_disturbance = detect_column_with_disturbance(df)

        # detect the disturbance
        sheet_values["disturbance_start_index"], \
            sheet_values["disturbance_start_month"], \
            sheet_values["disturbance_end_index"], \
            sheet_values["disturbance_end_month"], \
            sheet_values["disturbance_magnitude"] = detect_disturbance(df, column_with_disturbance)

        # detect effect on otd
        column_with_effect = f"Run {key}: Inventory Management.KPI: Lagerfüllgrad"
        threshold_lb = 0.99
        threshold_ub = 1.01
        sheet_values["otd_effect_start_index"], \
            sheet_values["otd_effect_start_month"], \
            sheet_values["otd_effect_end_index"], \
            sheet_values["otd_effect_end_month"], \
            sheet_values["otd_effect_initial_value"], \
            sheet_values["otd_effect_min_value"], \
            sheet_values["otd_effect_max_value"] = detect_effect(df, sheet_values, column_with_effect, threshold_lb, threshold_ub)

        # detect effect on cost
        column_with_effect = f"Run {key}: Bewertung.KPI: Kostenanteil an Umsatz"
        threshold_lb = 0.94
        threshold_ub = 1.06
        sheet_values["cost_effect_start_index"], \
            sheet_values["cost_effect_start_month"], \
            sheet_values["cost_effect_end_index"], \
            sheet_values["cost_effect_end_month"], \
            sheet_values["cost_effect_initial_value"], \
            sheet_values["cost_effect_min_value"], \
            sheet_values["cost_effect_max_value"] = detect_effect(df, sheet_values, column_with_effect, threshold_lb, threshold_ub)

        # detect effect on capacity
        column_with_effect = f"Run {key}: Production capacity.KPI: Kapazitätsauslastung"
        threshold_lb = 0.99
        threshold_ub = 1.01
        sheet_values["capacity_effect_start_index"], \
            sheet_values["capacity_effect_start_month"], \
            sheet_values["capacity_effect_end_index"], \
            sheet_values["capacity_effect_end_month"], \
            sheet_values["capacity_effect_initial_value"], \
            sheet_values["capacity_effect_min_value"], \
            sheet_values["capacity_effect_max_value"] = detect_effect(df, sheet_values, column_with_effect, threshold_lb, threshold_ub)

        results.loc[key] = sheet_values

    return results

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def calculate_kpis(results):

    file_kpis = dict()

    # calculate hardness
    # file_kpis["otd_hardness"], \
    #     file_kpis["cost_hardness"], \
    #     file_kpis["capacity_hardness"] = calculate_hardness(results)

    # calculate robustness
    file_kpis["otd_robustness"], \
        file_kpis["cost_robustness"], \
        file_kpis["capacity_robustness"] = calculate_robustness(results)

    # calculate recover_rapidity
    file_kpis["otd_recover_rapidity"], \
        file_kpis["cost_recover_rapidity"], \
        file_kpis["capacity_recover_rapidity"] = calculate_recover_rapidity(results)

    kpis = pd.DataFrame(file_kpis)

    return kpis

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def normalize_kpis(kpis):

    normalized_file_kpis = dict()
    for column in kpis.columns:
        normalized_file_kpis[column] = calculate_normalized_kpis(kpis[column])

    normalized_kpis = pd.DataFrame(normalized_file_kpis)

    return normalized_kpis

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def create_heatmaps(kpis):

    # Define custom color map
    cmap = sns.diverging_palette(150, 275, s=80, l=50, n=9, as_cmap=True)

    # create subplots
    fig, axes = plt.subplots(ncols=3, figsize=(10, 5))

    # Create heatmap with custom color map
    df = kpis.loc[:, ['otd_robustness', 'otd_recover_rapidity']]  # 'otd_hardness',
    sns.heatmap(df, annot=True, cbar=True, vmin=0, vmax=1, ax=axes[0], fmt=".3f")
    axes[0].set_title('KPIs on OTD', fontsize=12)

    # Create heatmap with custom color map
    df = kpis.loc[:, ['cost_robustness', 'cost_recover_rapidity']]  # 'cost_hardness',
    sns.heatmap(df, annot=True, cbar=True, vmin=0, vmax=1, ax=axes[1], fmt=".3f")
    axes[1].set_title('KPIs on cost', fontsize=12)

    # Create heatmap with custom color map
    df = kpis.loc[:, ['capacity_robustness', 'capacity_recover_rapidity']]  # 'capacity_hardness',
    sns.heatmap(df, annot=True, cbar=True, vmin=0, vmax=1, ax=axes[2], fmt=".3f")
    axes[2].set_title('KPIs on capacity', fontsize=12)

    plt.suptitle("Resultate")
    plt.tight_layout()
    # TODO: Switch for streamlit!
    #plt.show()
    st.write(fig)

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def main(csv_file):

    dfs = read_csv(csv_file=csv_file)
    # params = extract_params(dfs=dfs)
    results = analyze_dfs(dfs=dfs)
    kpis = calculate_kpis(results=results)
    normalized_kpis = normalize_kpis(kpis)
    create_heatmaps(normalized_kpis)

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

if __name__ == "__main__":

    CSV_FILE = Path.cwd() / "Data" / "data-export.csv"
    main(CSV_FILE)

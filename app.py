# app.py - Symposium Edition

from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import numpy as np
import copy
import mysql.connector
from mysql.connector import Error
import pandas as pd
from datetime import datetime
import os
import json
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import time
from dotenv import load_dotenv

load_dotenv()  # reads the .env file in the project folder

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-only-change-me')

# Global constant for fertilizer cost
FERTILIZER_COST = 25  # Rs per kg

# Track optimization statistics
optimization_stats = {
    'total_optimizations': 0,
    'total_time_saved': 0,
    'avg_execution_time': 0
}

# Demo scenarios for quick presentation
DEMO_SCENARIOS = {
    'small': {
        'name': 'Small Farmer Scenario',
        'description': 'Typical small-scale farming with limited resources',
        'crops': [
            {'name': 'Wheat', 'quantity': 50},
            {'name': 'Rice', 'quantity': 30}
        ],
        'fields': [
            {'region': 'PB', 'water': 500000, 'area': 40},
            {'region': 'HR', 'water': 300000, 'area': 30}
        ]
    },
    'medium': {
        'name': 'Cooperative Farming',
        'description': 'Medium-scale cooperative with diverse crops',
        'crops': [
            {'name': 'Wheat', 'quantity': 100},
            {'name': 'Rice', 'quantity': 80},
            {'name': 'Cotton', 'quantity': 60},
            {'name': 'Maize', 'quantity': 50}
        ],
        'fields': [
            {'region': 'PB', 'water': 1000000, 'area': 100},
            {'region': 'HR', 'water': 800000, 'area': 80},
            {'region': 'UP', 'water': 600000, 'area': 70}
        ]
    },
    'water_scarce': {
        'name': 'Water-Scarce Region',
        'description': 'Optimization for drought-prone areas',
        'crops': [
            {'name': 'Bajra', 'quantity': 40},
            {'name': 'Jowar', 'quantity': 35},
            {'name': 'Groundnut', 'quantity': 30}
        ],
        'fields': [
            {'region': 'RJ', 'water': 200000, 'area': 50},
            {'region': 'GJ', 'water': 150000, 'area': 40}
        ]
    }
}

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'optimization_project'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '')
}

def connect_to_database():
    """Establish connection to MySQL database."""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def get_available_crops():
    """Get list of all available crops from database."""
    connection = connect_to_database()
    if not connection:
        return []
    
    cursor = connection.cursor()
    query = "SELECT DISTINCT Crop FROM cropdata ORDER BY Crop"
    cursor.execute(query)
    crops = [row[0] for row in cursor.fetchall()]
    cursor.close()
    connection.close()
    return crops

def get_available_regions():
    """Get list of all available regions from database with details."""
    connection = connect_to_database()
    if not connection:
        return []
    
    cursor = connection.cursor()
    query = """
    SELECT DISTINCT Field_id, Representative_District, Soil_Type, 
           `Annual_Rainfall (mm)` as rainfall
    FROM fielddata 
    ORDER BY Field_id
    """
    cursor.execute(query)
    regions = []
    for row in cursor.fetchall():
        regions.append({
            'id': row[0],
            'district': row[1],
            'soil': row[2],
            'rainfall': row[3]
        })
    cursor.close()
    connection.close()
    return regions

def get_crop_data_from_db(crop_names):
    """Fetch crop data from database for given crop names."""
    connection = connect_to_database()
    if not connection:
        return {}
    
    cursor = connection.cursor(dictionary=True)
    crop_data = {}
    
    for crop in crop_names:
        query = "SELECT * FROM cropdata WHERE Crop = %s"
        cursor.execute(query, (crop,))
        result = cursor.fetchone()
        
        if result:
            # Map database columns with spaces to expected keys
            mapped_result = {
                'Yield_t_ha': float(result.get('Yield (t/ha)', 0)),
                'Market_Price_Rs_per_ton': float(result.get('Market Price (Rs/ton)', 0)),
                'Fertilizer_Use_kg_ha': float(result.get('Fertilizer Use (kg/ha)', 0)),
                'Water_Use_L_ha': float(result.get('Water Use (L/ha)', 0)),
                'Type': result.get('Type', '')
            }
            crop_data[crop] = mapped_result
    
    cursor.close()
    connection.close()
    return crop_data

def get_field_data_from_db(field_regions):
    """Fetch field data from database for given regions."""
    connection = connect_to_database()
    if not connection:
        return {}
    
    cursor = connection.cursor(dictionary=True)
    field_data = {}
    
    for region in field_regions:
        query = "SELECT * FROM fielddata WHERE Field_id = %s"
        cursor.execute(query, (region.upper(),))
        result = cursor.fetchone()
        
        if result:
            # Map to expected keys - no changes needed as column names match
            field_data[region] = {
                'Field_id': result.get('Field_id'),
                'Soil_Type': result.get('Soil_Type'),
                'Annual_Rainfall (mm)': float(result.get('Annual_Rainfall (mm)', 0)),
                'Rainfall_Index': float(result.get('Rainfall_Index', 0)),
                'Scarcity_Index': float(result.get('Scarcity_Index', 0)),
                'Alpha': float(result.get('Alpha', 0.002)),
                'Beta': float(result.get('Beta', 0.01)),
                'Gamma': float(result.get('Gamma', 0.001)),
                'Representative_District': result.get('Representative_District', '')
            }
        else:
            # If region not found, use default values
            print(f"Warning: Region {region} not found in database. Using defaults.")
            field_data[region] = {
                'Field_id': region,
                'Soil_Type': 'Loam',
                'Annual_Rainfall (mm)': 800,
                'Rainfall_Index': 0.5,
                'Scarcity_Index': 0.5,
                'Alpha': 0.002,
                'Beta': 0.01,
                'Gamma': 0.001,
                'Representative_District': 'Unknown'
            }
    
    cursor.close()
    connection.close()
    return field_data

# [Include all the optimization functions - same as before]
def calculate_cost_matrices(crop_data, field_data, crop_names, field_regions):
    """Calculate all three cost matrices based on the new formulas."""
    num_crops = len(crop_names)
    num_fields = len(field_regions)
    
    profit_cost_matrix = np.zeros((num_crops, num_fields))
    sustain_cost_matrix = np.zeros((num_crops, num_fields))
    hybrid_cost_matrix = np.zeros((num_crops, num_fields))
    
    for i, crop in enumerate(crop_names):
        if crop not in crop_data:
            continue
            
        crop_info = crop_data[crop]
        Yi = float(crop_info.get('Yield_t_ha', 0))
        Pi = float(crop_info.get('Market_Price_Rs_per_ton', 0))
        Fi = float(crop_info.get('Fertilizer_Use_kg_ha', 0))
        Wi = float(crop_info.get('Water_Use_L_ha', 0))
        
        for j, region in enumerate(field_regions):
            if region not in field_data:
                continue
                
            field_info = field_data[region]
            RIj = float(field_info.get('Rainfall_Index', 0))
            alpha = float(field_info.get('Alpha', 0))
            beta = float(field_info.get('Beta', 0))
            gamma = float(field_info.get('Gamma', 0))
            
            profit = Yi * Pi - Fi * FERTILIZER_COST
            profit_cost_matrix[i][j] = -profit
            
            sustain_cost = beta * (Fi * FERTILIZER_COST) + alpha * (Wi * (1 - RIj))
            sustain_cost_matrix[i][j] = sustain_cost
            
            hybrid_cost = gamma * profit + sustain_cost
            hybrid_cost_matrix[i][j] = hybrid_cost
    
    return profit_cost_matrix, sustain_cost_matrix, hybrid_cost_matrix

def check_balanced(supply, demand):
    total_supply = np.sum(supply)
    total_demand = np.sum(demand)
    
    if total_supply == total_demand:
        return True, supply, demand
    elif total_supply > total_demand:
        demand = np.append(demand, total_supply - total_demand)
        return False, supply, demand
    else:
        supply = np.append(supply, total_demand - total_supply)
        return False, supply, demand

def find_row_penalties(cost_matrix, remaining_rows, remaining_cols):
    row_penalties = []
    for i in remaining_rows:
        if len(remaining_cols) <= 1:
            row_penalties.append(float('inf'))
            continue
        row_costs = [cost_matrix[i][j] for j in remaining_cols]
        row_costs.sort()
        penalty = row_costs[1] - row_costs[0]
        row_penalties.append(penalty)
    return row_penalties

def find_col_penalties(cost_matrix, remaining_rows, remaining_cols):
    col_penalties = []
    for j in remaining_cols:
        if len(remaining_rows) <= 1:
            col_penalties.append(float('inf'))
            continue
        col_costs = [cost_matrix[i][j] for i in remaining_rows]
        col_costs.sort()
        penalty = col_costs[1] - col_costs[0]
        col_penalties.append(penalty)
    return col_penalties

def find_min_cost_cell(cost_matrix, row, col, remaining_rows, remaining_cols):
    min_cost = float('inf')
    min_i, min_j = -1, -1
    
    if row != -1:
        for j in remaining_cols:
            if cost_matrix[row][j] < min_cost:
                min_cost = cost_matrix[row][j]
                min_i, min_j = row, j
    else:
        for i in remaining_rows:
            if cost_matrix[i][col] < min_cost:
                min_cost = cost_matrix[i][col]
                min_i, min_j = i, col
    
    return min_i, min_j

def vogels_method(cost_matrix, supply, demand):
    m, n = len(supply), len(demand)
    cost = copy.deepcopy(cost_matrix)
    remaining_rows = list(range(m))
    remaining_cols = list(range(n))
    x = np.zeros((m, n))
    
    while remaining_rows and remaining_cols:
        row_penalties = find_row_penalties(cost, remaining_rows, remaining_cols)
        col_penalties = find_col_penalties(cost, remaining_rows, remaining_cols)
        
        max_row_penalty = max(row_penalties) if row_penalties else -float('inf')
        max_col_penalty = max(col_penalties) if col_penalties else -float('inf')
        
        if max_row_penalty >= max_col_penalty and max_row_penalty != -float('inf'):
            max_penalty_row_idx = row_penalties.index(max_row_penalty)
            selected_row = remaining_rows[max_penalty_row_idx]
            selected_col = -1
        else:
            max_penalty_col_idx = col_penalties.index(max_col_penalty)
            selected_row = -1
            selected_col = remaining_cols[max_penalty_col_idx]
        
        i, j = find_min_cost_cell(cost, selected_row, selected_col, remaining_rows, remaining_cols)
        allocation = min(supply[i], demand[j])
        x[i][j] = allocation
        
        supply[i] -= allocation
        demand[j] -= allocation
        
        if supply[i] == 0 and i in remaining_rows:
            remaining_rows.remove(i)
        if demand[j] == 0 and j in remaining_cols:
            remaining_cols.remove(j)
    
    return x

def is_solution_degenerate(solution, m, n):
    positives = np.sum(solution > 0)
    return positives < m + n - 1

def add_epsilon(solution, m, n):
    epsilon = 1e-10
    new_solution = solution.copy()
    positives = np.sum(new_solution > 0)
    need_to_add = m + n - 1 - positives
    
    added = 0
    for i in range(m):
        for j in range(n):
            if new_solution[i, j] == 0:
                has_row_alloc = any(new_solution[i, jj] > 0 for jj in range(n) if jj != j)
                has_col_alloc = any(new_solution[ii, j] > 0 for ii in range(m) if ii != i)
                
                if has_row_alloc and has_col_alloc:
                    new_solution[i, j] = epsilon
                    added += 1
                    if added == need_to_add:
                        return new_solution
    
    if added < need_to_add:
        for i in range(m):
            for j in range(n):
                if new_solution[i, j] == 0:
                    new_solution[i, j] = epsilon
                    added += 1
                    if added == need_to_add:
                        return new_solution
    
    return new_solution

def compute_ui_vj(solution, cost_matrix, m, n):
    ui = [None] * m
    vj = [None] * n
    ui[0] = 0
    
    allocated_cells = [(i, j) for i in range(m) for j in range(n) if solution[i, j] > 0]
    
    while None in ui or None in vj:
        progress = False
        
        for i, j in allocated_cells:
            if ui[i] is not None and vj[j] is None:
                vj[j] = cost_matrix[i, j] - ui[i]
                progress = True
            elif ui[i] is None and vj[j] is not None:
                ui[i] = cost_matrix[i, j] - vj[j]
                progress = True
        
        if not progress:
            for i in range(m):
                if ui[i] is None:
                    ui[i] = 0
                    break
    
    return ui, vj

def calculate_opportunity_costs(cost_matrix, ui, vj, m, n):
    opportunity_costs = np.zeros((m, n))
    for i in range(m):
        for j in range(n):
            opportunity_costs[i, j] = cost_matrix[i, j] - ui[i] - vj[j]
    return opportunity_costs

def find_most_negative_opportunity_cost(opportunity_costs, solution):
    min_cost = float('inf')
    min_i, min_j = -1, -1
    
    m, n = opportunity_costs.shape
    for i in range(m):
        for j in range(n):
            if solution[i, j] == 0 and opportunity_costs[i, j] < min_cost:
                min_cost = opportunity_costs[i, j]
                min_i, min_j = i, j
    
    return min_i, min_j, min_cost

def find_closed_loop(entering_cell, solution):
    i_enter, j_enter = entering_cell
    m, n = solution.shape
    loop_matrix = np.zeros_like(solution)
    
    def find_path(current_i, current_j, horiz_next, path):
        path.append((current_i, current_j))
        
        if len(path) > 1 and current_i == i_enter and current_j == j_enter:
            return True
        
        if horiz_next:
            for j in range(n):
                if j != current_j and (solution[current_i, j] > 0 or (current_i == i_enter and j == j_enter)):
                    if (current_i, j) not in path:
                        if find_path(current_i, j, False, path):
                            return True
        else:
            for i in range(m):
                if i != current_i and (solution[i, current_j] > 0 or (i == i_enter and current_j == j_enter)):
                    if (i, current_j) not in path:
                        if find_path(i, current_j, True, path):
                            return True
        
        path.pop()
        return False
    
    path = []
    find_path(i_enter, j_enter, True, path)
    
    if not path:
        path = []
        find_path(i_enter, j_enter, False, path)
    
    for i in range(len(path)):
        loop_matrix[path[i][0], path[i][1]] = 1 if i % 2 == 0 else -1
    
    return loop_matrix

def apply_loop(solution, loop_matrix):
    min_allocation = float('inf')
    
    for i in range(solution.shape[0]):
        for j in range(solution.shape[1]):
            if loop_matrix[i, j] == -1 and solution[i, j] > 0:
                min_allocation = min(min_allocation, solution[i, j])
    
    for i in range(solution.shape[0]):
        for j in range(solution.shape[1]):
            if loop_matrix[i, j] == 1:
                solution[i, j] += min_allocation
            elif loop_matrix[i, j] == -1:
                solution[i, j] -= min_allocation
    
    return solution

def modi_method(initial_solution, cost_matrix, m, n):
    solution = initial_solution.copy()
    
    if is_solution_degenerate(solution, m, n):
        solution = add_epsilon(solution, m, n)
    
    iteration = 1
    max_iterations = 50
    modi_iterations = 0
    
    while iteration <= max_iterations:
        ui, vj = compute_ui_vj(solution, cost_matrix, m, n)
        opportunity_costs = calculate_opportunity_costs(cost_matrix, ui, vj, m, n)
        enter_i, enter_j, min_cost = find_most_negative_opportunity_cost(opportunity_costs, solution)
        
        if min_cost >= -1e-10:
            modi_iterations = iteration
            break
        
        loop_matrix = find_closed_loop((enter_i, enter_j), solution)
        solution = apply_loop(solution, loop_matrix)
        
        if is_solution_degenerate(solution, m, n):
            solution = add_epsilon(solution, m, n)
        
        iteration += 1
    
    return solution, modi_iterations

def create_visualizations(solution, cost_matrix, crop_names, field_names, crop_data, field_data):
    """Create all visualizations and return as base64 encoded strings."""
    visualizations = {}
    
    # 1. Allocation Heatmap with better styling
    plt.figure(figsize=(12, 8))
    mask = solution == 0
    
    # Use a built-in colormap instead of custom blend
    sns.heatmap(solution, annot=True, fmt='.1f', xticklabels=field_names, 
                yticklabels=crop_names, cmap='YlGn', mask=mask,
                cbar_kws={'label': 'Allocation (units)'}, 
                linewidths=1, linecolor='lightgray',
                annot_kws={'fontsize': 12, 'weight': 'bold'})
    
    plt.title('Optimal Crop Allocation Matrix', fontsize=18, weight='bold', pad=20)
    plt.xlabel('Fields', fontsize=14, weight='bold')
    plt.ylabel('Crops', fontsize=14, weight='bold')
    plt.tight_layout()
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    img_buffer.seek(0)
    visualizations['heatmap'] = base64.b64encode(img_buffer.getvalue()).decode()
    plt.close()
    
    # 2. Enhanced Resource Usage Charts
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    water_usage = []
    fertilizer_usage = []
    fields_no_dummy = []
    
    for j, field in enumerate(field_names):
        if field == "Dummy":
            continue
            
        water_used = 0
        fertilizer_used = 0
        
        for i, crop in enumerate(crop_names):
            if crop == "Dummy" or crop not in crop_data:
                continue
                
            if solution[i, j] > 0:
                water_used += solution[i, j] * float(crop_data[crop]['Water_Use_L_ha'])
                fertilizer_used += solution[i, j] * float(crop_data[crop]['Fertilizer_Use_kg_ha'])
        
        water_usage.append(water_used / 1000)  # Convert to thousands
        fertilizer_usage.append(fertilizer_used)
        fields_no_dummy.append(field)
    
    if water_usage:
        # Water usage chart
        bars1 = ax1.bar(fields_no_dummy, water_usage, color='#2196F3', edgecolor='darkblue', linewidth=2)
        ax1.set_xlabel('Fields', fontsize=14, weight='bold')
        ax1.set_ylabel('Water Usage (Thousands of Liters)', fontsize=14, weight='bold')
        ax1.set_title('Water Consumption by Field', fontsize=16, weight='bold')
        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Add value labels
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.0f}K', ha='center', va='bottom', fontsize=11, weight='bold')
        
        # Fertilizer usage chart
        bars2 = ax2.bar(fields_no_dummy, fertilizer_usage, color='#4CAF50', edgecolor='darkgreen', linewidth=2)
        ax2.set_xlabel('Fields', fontsize=14, weight='bold')
        ax2.set_ylabel('Fertilizer Usage (kg)', fontsize=14, weight='bold')
        ax2.set_title('Fertilizer Consumption by Field', fontsize=16, weight='bold')
        ax2.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Add value labels
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.0f}', ha='center', va='bottom', fontsize=11, weight='bold')
    
    plt.suptitle('Resource Usage Analysis', fontsize=18, weight='bold')
    plt.tight_layout()
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    img_buffer.seek(0)
    visualizations['resource_usage'] = base64.b64encode(img_buffer.getvalue()).decode()
    plt.close()
    
    # 3. Enhanced Crop Distribution Pie Chart
    plt.figure(figsize=(10, 10))
    
    crop_totals = []
    crop_labels = []
    
    for i, crop in enumerate(crop_names):
        if crop == "Dummy":
            continue
        total = sum(solution[i, j] for j in range(len(field_names)))
        if total > 0:
            crop_totals.append(total)
            crop_labels.append(f"{crop}\n{total:.1f} units")
    
    if crop_totals:
        colors = plt.cm.Set3(range(len(crop_totals)))
        wedges, texts, autotexts = plt.pie(crop_totals, labels=crop_labels, colors=colors, 
                                           autopct='%1.1f%%', startangle=90,
                                           textprops={'fontsize': 12, 'weight': 'bold'},
                                           pctdistance=0.85)
        
        # Add a circle at the center to make it a donut chart
        centre_circle = plt.Circle((0,0), 0.70, fc='white', linewidth=2, edgecolor='gray')
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
        
        plt.title('Crop Distribution Overview', fontsize=18, weight='bold', pad=20)
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    img_buffer.seek(0)
    visualizations['pie_chart'] = base64.b64encode(img_buffer.getvalue()).decode()
    plt.close()
    
    return visualizations

@app.route('/')
def index():
    """Home page - redirect to welcome for symposium"""
    return redirect(url_for('welcome'))

@app.route('/welcome')
def welcome():
    """Symposium welcome page"""
    return render_template('welcome.html')

@app.route('/app')
def application():
    """Main application page"""
    crops = get_available_crops()
    regions = get_available_regions()
    return render_template('app.html', crops=crops, regions=regions)

@app.route('/demo/<scenario>')
def load_demo(scenario):
    """Load demo scenarios for presentation"""
    if scenario in DEMO_SCENARIOS:
        return jsonify({
            'success': True,
            'scenario': DEMO_SCENARIOS[scenario]
        })
    return jsonify({'success': False, 'error': 'Scenario not found'})

@app.route('/optimize', methods=['POST'])
def optimize():
    """Run optimization based on user inputs."""
    try:
        start_time = time.time()
        data = request.json
        
        # Extract inputs
        crop_inputs = data['crops']
        field_inputs = data['fields']
        optimization_type = int(data['optimization_type'])
        
        # Prepare data
        crop_names = [c['name'] for c in crop_inputs]
        crop_supplies = np.array([float(c['quantity']) for c in crop_inputs])
        
        field_regions = [f['region'] for f in field_inputs]
        field_areas = np.array([float(f['area']) for f in field_inputs])
        field_water = [float(f['water']) for f in field_inputs]
        
        # Fetch data from database
        crop_data = get_crop_data_from_db(crop_names)
        field_data = get_field_data_from_db(field_regions)
        
        # Calculate cost matrices
        profit_matrix, sustain_matrix, hybrid_matrix = calculate_cost_matrices(
            crop_data, field_data, crop_names, field_regions
        )
        
        # Select appropriate cost matrix
        if optimization_type == 1:
            cost_matrix = profit_matrix
            scenario_name = "Profit Focused"
        elif optimization_type == 2:
            cost_matrix = sustain_matrix
            scenario_name = "Sustainability Focused"
        else:
            cost_matrix = hybrid_matrix
            scenario_name = "Hybrid Approach"
        
        # Use field areas as demand
        demand = field_areas
        supply = crop_supplies
        
        # Check if balanced
        is_balanced, supply_copy, demand_copy = check_balanced(supply.copy(), demand.copy())
        
        # Update names if dummy added
        current_field_names = field_regions.copy()
        if len(demand_copy) > len(field_regions):
            current_field_names.append("Dummy")
            dummy_col = np.zeros((cost_matrix.shape[0], 1))
            cost_matrix = np.hstack([cost_matrix, dummy_col])
        
        current_crop_names = crop_names.copy()
        if len(supply_copy) > len(crop_names):
            current_crop_names.append("Dummy")
            dummy_row = np.zeros((1, cost_matrix.shape[1]))
            cost_matrix = np.vstack([cost_matrix, dummy_row])
        
        # Solve using VAM
        vam_start = time.time()
        initial_solution = vogels_method(cost_matrix, supply_copy.copy(), demand_copy.copy())
        vam_time = time.time() - vam_start
        initial_cost = np.sum(initial_solution * cost_matrix)
        
        # Optimize using MODI
        modi_start = time.time()
        final_solution, modi_iterations = modi_method(initial_solution, cost_matrix, 
                                                     len(supply_copy), len(demand_copy))
        modi_time = time.time() - modi_start
        final_cost = np.sum(final_solution * cost_matrix)
        
        # Total execution time
        total_time = time.time() - start_time
        
        # Update global statistics
        optimization_stats['total_optimizations'] += 1
        optimization_stats['total_time_saved'] += (initial_cost - final_cost)
        optimization_stats['avg_execution_time'] = (optimization_stats['avg_execution_time'] * 
                                                   (optimization_stats['total_optimizations'] - 1) + 
                                                   total_time) / optimization_stats['total_optimizations']
        
        # Create visualizations
        visualizations = create_visualizations(
            final_solution, cost_matrix, current_crop_names, 
            current_field_names, crop_data, field_data
        )
        
        # Prepare allocation data
        allocation_data = []
        for i, crop in enumerate(current_crop_names):
            for j, field in enumerate(current_field_names):
                if final_solution[i, j] > 0:
                    allocation_data.append({
                        'crop': crop,
                        'field': field,
                        'amount': float(final_solution[i, j])
                    })
        
        # Calculate environmental impact
        total_water_used = 0
        total_fertilizer_used = 0
        for i, crop in enumerate(current_crop_names):
            if crop != "Dummy" and crop in crop_data:
                for j in range(len(current_field_names)):
                    if final_solution[i, j] > 0:
                        total_water_used += final_solution[i, j] * crop_data[crop]['Water_Use_L_ha']
                        total_fertilizer_used += final_solution[i, j] * crop_data[crop]['Fertilizer_Use_kg_ha']
        
        # Summary statistics
        summary = {
            'scenario': scenario_name,
            'initial_cost': float(initial_cost),
            'final_cost': float(final_cost),
            'cost_reduction': float(initial_cost - final_cost),
            'cost_reduction_percent': float((initial_cost - final_cost) / abs(initial_cost) * 100) if initial_cost != 0 else 0,
            'total_allocated': float(np.sum(final_solution)),
            'optimization_type': optimization_type,
            'total_water_used': float(total_water_used),
            'total_fertilizer_used': float(total_fertilizer_used),
            'performance': {
                'vam_time': round(vam_time, 3),
                'modi_time': round(modi_time, 3),
                'modi_iterations': modi_iterations,
                'total_time': round(total_time, 3)
            }
        }
        
        # Water feasibility check
        water_check = []
        for j, field in enumerate(current_field_names):
            if field == "Dummy":
                continue
    
        water_required = 0
        for i, crop in enumerate(current_crop_names):
            if crop == "Dummy" or crop not in crop_data:
                continue
            if final_solution[i, j] > 0:
                water_required += final_solution[i, j] * float(crop_data[crop]['Water_Use_L_ha'])
    
        water_available = field_water[j] if j < len(field_water) else 0
        water_check.append({
        'field': field,
        'required': float(water_required),  # Ensure it's a float
        'available': float(water_available),  # Ensure it's a float
        'feasible': bool(water_required <= water_available),  # Convert to Python bool
        'utilization': float((water_required / water_available * 100) if water_available > 0 else 0)
        })
        
        return jsonify({
            'success': True,
            'allocation': allocation_data,
            'summary': summary,
            'visualizations': visualizations,
            'water_check': water_check,
            'solution_matrix': final_solution.tolist(),
            'crop_names': current_crop_names,
            'field_names': current_field_names
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/stats')
def get_stats():
    """Return current optimization statistics"""
    return jsonify(optimization_stats)

@app.route('/compare', methods=['POST'])
def compare_scenarios():
    """Compare all three optimization approaches"""
    try:
        data = request.json
        comparison_results = []
        
        # Run optimization for each type
        for opt_type in [1, 2, 3]:
            data['optimization_type'] = opt_type
            # Call optimize function logic here
            # Store results
            pass
        
        return jsonify({
            'success': True,
            'comparison': comparison_results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/export', methods=['POST'])
def export_excel():
    """Export results to Excel file."""
    try:
        data = request.json
        
        # Reconstruct the solution matrix
        solution = np.array(data['solution_matrix'])
        crop_names = data['crop_names']
        field_names = data['field_names']
        
        # Create Excel file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"crop_allocation_{timestamp}.xlsx"
        
        # Create dataframes
        allocation_df = pd.DataFrame(solution, index=crop_names, columns=field_names)
        summary_df = pd.DataFrame([data['summary']])
        
        # Create Excel writer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            allocation_df.to_excel(writer, sheet_name='Allocation Matrix')
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Format the Excel file
            workbook = writer.book
            format1 = workbook.add_format({'num_format': '#,##0.00'})
            format2 = workbook.add_format({'num_format': '0.00%'})
            
            # Auto-adjust columns
            for sheet in writer.sheets.values():
                sheet.set_column('A:Z', 15)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=os.getenv('FLASK_DEBUG') == '1')

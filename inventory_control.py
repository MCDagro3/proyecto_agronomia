#!/usr/bin/env python3
"""
Problema de Control Estocástico: Gestión de Inventario

Este código implementa y compara:
1. Distribución CONOCIDA: Solución óptima (s, S) analítica
2. Distribución DESCONOCIDA: Aprendizaje por Refuerzo (Q-Learning)
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm, poisson
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURACIÓN DEL PROBLEMA
# ============================================================================

class InventoryProblem:
    """Clase base que define el problema de inventario"""
    
    def __init__(self, 
                 h=1.0,      # Coste de almacenamiento por unidad
                 p=5.0,      # Coste de escasez por unidad
                 c=2.0,      # Coste variable de pedido por unidad
                 K=50.0,     # Coste fijo de pedido
                 beta=0.95,  # Factor de descuento
                 max_inventory=50,
                 max_order=30,
                 seed=42):
        
        self.h = h
        self.p = p
        self.c = c
        self.K = K
        self.beta = beta
        self.max_inventory = max_inventory
        self.max_order = max_order
        self.rng = np.random.default_rng(seed)
        
    def demand_distribution(self, demand_type='known'):
        """Define la distribución de demanda"""
        if demand_type == 'known':
            # Demanda ~ Poisson(λ=10) - conocida
            return PoissonDemand(10, self.rng)
        elif demand_type == 'unknown':
            # Demanda ~ Poisson(λ=10) - pero el agente no la conoce
            return PoissonDemand(10, self.rng)
        else:
            raise ValueError(f"Demand type {demand_type} not recognized")
    
    def holding_shortage_cost(self, inventory):
        """Calcula coste de almacenamiento o escasez"""
        if inventory > 0:
            return self.h * inventory
        else:
            return self.p * abs(inventory)
    
    def total_cost(self, inventory, order):
        """Calcula coste total en un período"""
        if order > 0:
            return self.K + self.c * order + self.holding_shortage_cost(inventory + order)
        else:
            return self.holding_shortage_cost(inventory)


# ============================================================================
# DISTRIBUCIONES DE DEMANDA
# ============================================================================

class PoissonDemand:
    """Demanda con distribución Poisson"""
    
    def __init__(self, lambda_param, rng):
        self.lambda_param = lambda_param
        self.rng = rng
        
    def sample(self):
        return max(0, int(self.rng.poisson(self.lambda_param)))
    
    def cdf(self, x):
        """Función de distribución acumulada"""
        from scipy.stats import poisson
        return poisson.cdf(x, self.lambda_param)
    
    def ppf(self, q):
        """Función inversa de la distribución acumulada (percentil)"""
        from scipy.stats import poisson
        return poisson.ppf(q, self.lambda_param)


# ============================================================================
# SOLUCIÓN ÓPTIMA - DISTRIBUCIÓN CONOCIDA
# ============================================================================

class KnownDistributionSolver:
    """Resuelve el problema cuando la distribución es conocida"""
    
    def __init__(self, problem, demand_dist, max_states=101, max_iter=1000, tol=1e-6):
        self.problem = problem
        self.demand_dist = demand_dist
        self.max_states = max_states
        
        # Estados posibles de inventario
        self.states = np.linspace(-50, 50, max_states).astype(int)
        self.state_to_idx = {s: i for i, s in enumerate(self.states)}
        
        # Acciones posibles (cantidad a ordenar)
        self.actions = list(range(problem.max_order + 1))
        
        # Valor inicial y política
        self.V = np.zeros(max_states)
        self.policy = np.zeros(max_states, dtype=int)
        
    def value_iteration(self):
        """Algoritmo de iteración de valor para encontrar política óptima"""
        for iteration in range(max_iter):
            V_new = np.zeros_like(self.V)
            policy_new = np.zeros_like(self.policy)
            
            for i, state in enumerate(self.states):
                min_val = np.inf
                best_action = 0
                
                for action in self.actions:
                    # Estado después de ordenar
                    y = min(state + action, self.problem.max_inventory)
                    
                    # Coste inmediato (promedio sobre todas las demandas posibles)
                    immediate_cost = problem.total_cost(state, action)
                    
                    # Coste futuro esperado (aproximado con muestreo)
                    future_cost = 0
                    for _ in range(100):  # Monte Carlo
                        d = demand_dist.sample()
                        next_state = max(y - d, -50)
                        next_state = min(next_state, 50)
                        if next_state in self.state_to_idx:
                            future_cost += self.V[self.state_to_idx[next_state]]
                    future_cost /= 100
                    
                    total_val = immediate_cost + problem.beta * future_cost
                    
                    if total_val < min_val:
                        min_val = total_val
                        best_action = action
                
                V_new[i] = min_val
                policy_new[i] = best_action
            
            # Verificar convergencia
            if np.max(np.abs(V_new - self.V)) < self.tol:
                break
                
            self.V = V_new
            self.policy = policy_new
        
        return self.extract_policy_parameters()
    
    def extract_policy_parameters(self):
        """Extrae parámetros (s, S) de la política óptima"""
        # Encontrar S: estado objetivo óptimo
        s_optimal = self.states[np.argmin(self.V)]
        
        # Encontrar s: umbral de reorden
        s_threshold = s_optimal
        for state in sorted(self.states):
            if self.policy[self.state_to_idx[state]] == 0:
                s_threshold = state
        
        return s_threshold, s_optimal


# ============================================================================
# DISTRIBUCIÓN DESCONOCIDA - Q-LEARNING
# ============================================================================

class UnknownDistributionSolver:
    """Resuelve el problema usando Q-Learning cuando la distribución es desconocida"""
    
    def __init__(self, problem, max_states=101, max_actions=31):
        self.problem = problem
        
        # Estados y acciones
        self.states = np.linspace(-50, 50, max_states).astype(int)
        self.state_to_idx = {s: i for i, s in enumerate(self.states)}
        self.actions = list(range(max_actions))
        
        # Q-table
        self.Q = np.zeros((max_states, max_actions))
        
        # Hiperparámetros Q-Learning
        self.alpha = 0.1  # Tasa de aprendizaje
        self.epsilon = 0.2  # Exploración
        self.beta = problem.beta
        
    def select_action(self, state, training=True):
        """Selección de acción con estrategia ε-greedy"""
        if training and self.problem.rng.random() < self.epsilon:
            return self.problem.rng.choice(self.actions)
        else:
            state_idx = self.state_to_idx.get(state, self.state_to_idx[0])
            return self.actions[np.argmax(self.Q[state_idx])]
    
    def train(self, n_episodes=5000, episode_length=100, decay_epsilon=True):
        """Entrenamiento del Q-Learning"""
        total_costs = []
        
        for episode in range(n_episodes):
            state = self.problem.rng.integers(-20, 20)
            episode_cost = 0
            
            for t in range(episode_length):
                # Seleccionar acción
                action = self.select_action(state, training=True)
                
                # Simular transición
                d = demand_dist.sample()
                next_state = state + action - d
                next_state = max(min(next_state, 50), -50)
                
                # Coste inmediato
                cost = problem.total_cost(state, action)
                episode_cost += cost
                
                # Actualizar Q-table
                state_idx = self.state_to_idx[state]
                next_state_idx = self.state_to_idx[next_state]
                max_future_q = np.max(self.Q[next_state_idx])
                
                td_target = cost + self.beta * max_future_q
                td_error = td_target - self.Q[state_idx, action]
                self.Q[state_idx, action] += self.alpha * td_error
                
                state = next_state
                
                # Decaer ε
                if decay_epsilon and episode % 100 == 0:
                    self.epsilon = max(0.05, self.epsilon * 0.999)
            
            total_costs.append(episode_cost)
        
        return total_costs
    
    def get_policy(self):
        """Obtener política greedy a partir de Q-table"""
        policy = np.zeros(len(self.states), dtype=int)
        for i in range(len(self.states)):
            policy[i] = self.actions[np.argmax(self.Q[i])]
        return policy


# ============================================================================
# POLÍTICAS PARA COMPARAR
# ============================================================================

class Policy:
    """Políticas para comparar"""
    
    @staticmethod
    def optimal_policy(state, s, S):
        """Política óptima (s, S)"""
        if state < s:
            return S - state
        else:
            return 0
    
    @staticmethod
    def fixed_threshold(state, threshold, order_amount):
        """Política de umbral fijo"""
        if state < threshold:
            return order_amount
        else:
            return 0
    
    @staticmethod
    def no_ordering(state):
        """Política de nunca ordenar"""
        return 0
    
    @staticmethod
    def always_order(state, order_amount=20):
        """Política de ordenar siempre"""
        return min(order_amount, 30)


# ============================================================================
# SIMULACIÓN Y COMPARACIÓN
# ============================================================================

def simulate_policy(problem, demand_dist, policy_func, policy_params, 
                    n_periods=500, seed=42, initial_inventory=10):
    """Simular una política a lo largo del tiempo"""
    rng = np.random.default_rng(seed)
    
    inventory = initial_inventory
    total_cost = 0
    inventory_history = [inventory]
    order_history = []
    demand_history = []
    
    for t in range(n_periods):
        # Generar demanda
        d = demand_dist.sample()
        demand_history.append(d)
        
        # Determinar orden según política
        if policy_func == Policy.optimal_policy:
            order = policy_func(inventory, *policy_params)
        elif policy_func == Policy.fixed_threshold:
            order = policy_func(inventory, *policy_params)
        elif policy_func == Policy.no_ordering:
            order = 0
        else:
            order = policy_func(inventory, *policy_params)
        
        order = min(order, problem.max_order)
        order_history.append(order)
        
        # Actualizar inventario
        inventory = inventory + order - d
        inventory = max(min(inventory, problem.max_inventory), problem.max_inventory)
        inventory_history.append(inventory)
        
        # Calcular coste
        cost = problem.total_cost(inventory - order, order)
        total_cost += cost
    
    return {
        'inventory': inventory_history,
        'orders': order_history,
        'demand': demand_history,
        'total_cost': total_cost,
        'avg_cost_per_period': total_cost / n_periods
    }


# ============================================================================
# GRÁFICOS
# ============================================================================

def plot_results(problem, demand_dist, results_known, results_unknown, 
                 results_fixed, results_no_order):
    """Generar gráficos de comparación"""
    
    fig, axes = plt.subplots(3, 2, figsize=(15, 12))
    fig.suptitle('Problema de Control Estocástico: Gestión de Inventario', 
                 fontsize=14, fontweight='bold')
    
    # Gráfico 1: Evolución del inventario
    ax = axes[0, 0]
    ax.plot(results_known['inventory'], label='Óptima (s, S)', linewidth=2)
    ax.plot(results_unknown['inventory'], label='Q-Learning', alpha=0.7)
    ax.plot(results_fixed['inventory'], label='Umbral Fijo', alpha=0.5, linestyle='--')
    ax.plot(results_no_order['inventory'], label='Sin Ordenar', alpha=0.3, linestyle=':')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5, alpha=0.3)
    ax.set_xlabel('Período')
    ax.set_ylabel('Nivel de Inventario')
    ax.set_title('Evolución del Inventario')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Gráfico 2: Costos acumulados
    ax = axes[0, 1]
    n_periods = len(results_known['total_cost'])
    periods = np.linspace(1, n_periods, n_periods)
    
    # Calcular costes acumulados
    known_costs = np.cumsum([sum([problem.total_cost(results_known['inventory'][i], 
                                                     results_known['orders'][i]) 
                                   for i in range(j+1)]) 
                              for j in range(n_periods)])
    
    ax.plot(range(n_periods), known_costs, label='Óptima (s, S)', linewidth=2)
    ax.set_xlabel('Período')
    ax.set_ylabel('Coste Acumulado')
    ax.set_title('Coste Acumulado vs Político Óptimo')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Gráfico 3: Histograma de órdenes
    ax = axes[1, 0]
    ax.hist(results_known['orders'], bins=15, alpha=0.6, label='Óptima (s, S)')
    ax.hist(results_unknown['orders'], bins=15, alpha=0.6, label='Q-Learning')
    ax.set_xlabel('Cantidad Ordenada')
    ax.set_ylabel('Frecuencia')
    ax.set_title('Distribución de Órdenes')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Gráfico 4: Comparación de costes finales
    ax = axes[1, 1]
    policies = ['Óptima (s,\nS)', 'Q-Learning', 'Umbral\nFijo', 'Sin\nOrdenar']
    costs = [
        results_known['avg_cost_per_period'],
        results_unknown['avg_cost_per_period'],
        results_fixed['avg_cost_per_period'],
        results_no_order['avg_cost_per_period']
    ]
    colors = ['green', 'blue', 'orange', 'red']
    ax.bar(policies, costs, color=colors, alpha=0.7, edgecolor='black')
    ax.set_ylabel('Coste Promedio por Período')
    ax.set_title('Comparación de Costes por Política')
    ax.tick_params(axis='x', rotation=0)
    for i, v in enumerate(costs):
        ax.text(i, v + 5, f'{v:.1f}', ha='center', fontweight='bold')
    
    # Gráfico 5: Estado del sistema (inventario vs órdenes)
    ax = axes[2, 0]
    ax.scatter(results_known['inventory'][:-1], results_known['orders'], 
               c=range(len(results_known['orders'])), cmap='viridis', 
               s=50, alpha=0.6, label='Óptima (s, S)')
    ax.scatter(results_unknown['inventory'][:-1], results_unknown['orders'],
               c='red', s=30, alpha=0.4, label='Q-Learning', marker='x')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
    ax.set_xlabel('Inventario antes de ordenar')
    ax.set_ylabel('Cantidad ordenada')
    ax.set_title('Política de Control: Inventario vs Órdenes')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Gráfico 6: Demanda vs Inventario
    ax = axes[2, 1]
    ax.plot(results_known['demand'], 'alpha=0.4', linewidth=1, label='Demanda')
    ax.plot(results_known['inventory'], linewidth=2, label='Inventario (Óptimo)')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5, alpha=0.3)
    ax.set_xlabel('Período')
    ax.set_ylabel('Cantidad')
    ax.set_title('Demanda vs Nivel de Inventario')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('inventory_control_comparison.png', dpi=150, bbox_inches='tight')
    print("Gráficos guardados en 'inventory_control_comparison.png'")
    plt.close()


# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================

if __name__ == '__main__':
    
    print("="*80)
    print("PROBLEMA DE CONTROL ESTOCÁSTICO - GESTIÓN DE INVENTARIO")
    print("="*80)
    
    # Crear instancia del problema
    problem = InventoryProblem(h=1.0, p=5.0, c=2.0, K=10.0, beta=0.95,
                               max_inventory=50, max_order=30, seed=42)
    
    # Distribución de demanda
    demand_dist = PoissonDemand(lambda_param=10, rng=np.random.default_rng(123))
    
    print("\n[1] DISTRIBUCIÓN CONOCIDA - Solución Óptima (s, S)")
    print("-"*80)
    
    # Resolver para distribución conocida
    known_solver = KnownDistributionSolver(problem, demand_dist)
    s_opt, S_opt = known_solver.value_iteration()
    print(f"Política Óptima (s, S): s = {s_opt}, S = {S_opt}")
    
    # Simular política óptima
    results_known = simulate_policy(
        problem, demand_dist,
        Policy.optimal_policy, (s_opt, S_opt),
        n_periods=500, initial_inventory=10
    )
    print(f"Coste promedio: {results_known['avg_cost_per_period']:.2f}")
    
    print("\n[2] DISTRIBUCIÓN DESCONOCIDA - Q-Learning")
    print("-"*80)
    
    # Resolver con Q-Learning (distribución desconocida)
    unknown_solver = UnknownDistributionSolver(problem)
    total_costs_train = unknown_solver.train(n_episodes=2000, episode_length=50)
    
    print(f"Coste promedio entrenamiento: {np.mean(total_costs_train[-100:]):.2f}")
    
    # Simular política aprendida
    unknown_policy = unknown_solver.get_policy()
    def unknown_policy_func(state):
        state_idx = unknown_solver.state_to_idx.get(state, 0)
        return unknown_policy[state_idx]
    
    results_unknown = simulate_policy(
        problem, demand_dist,
        unknown_policy_func, None,
        n_periods=500, initial_inventory=10
    )
    print(f"Coste promedio Q-Learning: {results_unknown['avg_cost_per_period']:.2f}")
    
    print("\n[3] COMPARACIÓN CON OTRAS POLÍTICAS")
    print("-"*80)
    
    # Políticas alternates
    results_fixed = simulate_policy(
        problem, demand_dist,
        Policy.fixed_threshold, (-10, 20),
        n_periods=500, initial_inventory=10
    )
    print(f"Umbral Fijo (threshold=-10, order=20): {results_fixed['avg_cost_per_period']:.2f}")
    
    results_no_order = simulate_policy(
        problem, demand_dist,
        Policy.no_ordering, None,
        n_periods=500, initial_inventory=10
    )
    print(f"Sin Ordenar: {results_no_order['avg_cost_per_period']:.2f}")
    
    # Generar gráficos
    print("\n[4] GENERANDO GRÁFICOS...")
    print("-"*80)
    
    plot_results(problem, demand_dist, results_known, results_unknown,
                 results_fixed, results_no_order)
    
    # Imprimir resumen
    print("\n" + "="*80)
    print("RESUMEN DE RESULTADOS")
    print("="*80)
    print(f"{'Política:':<20} {'Coste Promedio:':>15} {'Ratio vs Óptimo:':>18}")
    print("-"*55)
    print(f"{'Óptima (s, S)':<20} {results_known['avg_cost_per_period']:>15.2f} {'1.00x':>18}")
    print(f"{'Q-Learning':<20} {results_unknown['avg_cost_per_period']:>15.2f} "
          f"{results_unknown['avg_cost_per_period']/results_known['avg_cost_per_period']:>16.2f}x")
    print(f"{'Umbral Fijo':<20} {results_fixed['avg_cost_per_period']:>15.2f} "
          f"{results_fixed['avg_cost_per_period']/results_known['avg_cost_per_period']:>16.2f}x")
    print(f"{'Sin Ordenar':<20} {results_no_order['avg_cost_per_period']:>15.2f} "
          f"{results_no_order['avg_cost_per_period']/results_known['avg_cost_per_period']:>16.2f}x")
    
    print("\n[Conclusión]")
    print("La política óptima (s, S) minimiza los costes esperados.")
    print("Q-Learning aprende una aproximación sin conocer la distribución.")
    print("Políticas simples pueden ser subóptimas significativamente.")

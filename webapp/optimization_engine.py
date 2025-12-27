# webapp/optimization_engine.py
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import logging

logger = logging.getLogger("Optimizer")

class PortfolioOptimizer:
    def __init__(self, price_df, risk_free_rate=0.04, benchmark_returns=None,
                 group_constraints=None, ticker_groups=None):
        self.prices = price_df
        self.returns = self.prices.pct_change().dropna()
        self.rf_rate = risk_free_rate
        self.trading_days = 252
        self.mean_returns = self.returns.mean() * self.trading_days
        self.cov_matrix = self.returns.cov() * self.trading_days
        self.tickers = self.prices.columns.tolist()
        self.num_assets = len(self.tickers)
        self.benchmark_returns = benchmark_returns  # For tracking error optimization
        
        # Group constraints (Phase 3)
        self.group_constraints = group_constraints or {}
        self.ticker_groups = ticker_groups or {}
        self.group_constraint_matrix = None
        self.group_lower_bounds = None
        self.group_upper_bounds = None
        if self.group_constraints and self.ticker_groups:
            self._build_group_constraint_matrices()

    def performance_stats(self, weights):
        weights = np.array(weights)
        port_return = np.sum(self.mean_returns * weights)
        port_volatility = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        sharpe_ratio = (port_return - self.rf_rate) / port_volatility if port_volatility > 0 else 0
        return port_return, port_volatility, sharpe_ratio

    def advanced_stats(self, weights):
        weights = np.array(weights)
        port_daily_rets = self.returns.dot(weights)
        
        # Sortino
        negative_rets = port_daily_rets[port_daily_rets < 0]
        downside_std = negative_rets.std() * np.sqrt(self.trading_days) if len(negative_rets) > 0 else 1e-6
        expected_return = port_daily_rets.mean() * self.trading_days
        sortino = (expected_return - self.rf_rate) / downside_std if downside_std > 0 else 0

        # VaR & CVaR
        var_95 = np.percentile(port_daily_rets, 5)
        cvar_95 = port_daily_rets[port_daily_rets <= var_95].mean()

        # Drawdown
        cumulative = (1 + port_daily_rets).cumprod()
        peak = cumulative.expanding(min_periods=1).max()
        drawdown = (cumulative / peak) - 1
        max_drawdown = drawdown.min()

        return {
            "sortino_ratio": round(sortino, 2),
            "var_95_daily": round(var_95 * 100, 2),
            "cvar_95_daily": round(cvar_95 * 100, 2),
            "max_drawdown": round(max_drawdown * 100, 2)
        }

    # ========================================================================
    # GROUP CONSTRAINTS (Phase 3)
    # ========================================================================

    def _build_group_constraint_matrices(self):
        """Builds constraint matrices for group allocation limits"""
        unique_groups = sorted(set(self.ticker_groups.values()))
        n_groups = len(unique_groups)
        
        # Build group membership matrix
        A = np.zeros((n_groups, self.num_assets))
        for i, group in enumerate(unique_groups):
            for j, ticker in enumerate(self.tickers):
                if self.ticker_groups.get(ticker) == group:
                    A[i, j] = 1
        
        self.group_constraint_matrix = A
        self.group_lower_bounds = np.array([
            self.group_constraints.get(g, {}).get('min', 0.0) 
            for g in unique_groups
        ])
        self.group_upper_bounds = np.array([
            self.group_constraints.get(g, {}).get('max', 1.0) 
            for g in unique_groups
        ])
        logger.info(f"Built group constraints for {n_groups} groups: {unique_groups}")
    
    def _add_group_constraints_to_list(self, base_constraints):
        """Helper to add group constraints to constraint list"""
        if isinstance(base_constraints, dict):
            constraints = [base_constraints]
        elif isinstance(base_constraints, tuple):
            constraints = [base_constraints]
        else:
            constraints = list(base_constraints) if base_constraints else []
        
        if self.group_constraint_matrix is not None:
            for i in range(len(self.group_lower_bounds)):
                constraints.append({
                    'type': 'ineq',
                    'fun': lambda w, idx=i: (self.group_constraint_matrix[idx] @ w) - self.group_lower_bounds[idx]
                })
                constraints.append({
                    'type': 'ineq',
                    'fun': lambda w, idx=i: self.group_upper_bounds[idx] - (self.group_constraint_matrix[idx] @ w)
                })
        
        return constraints

    # ========================================================================
    # MEAN-VARIANCE OPTIMIZATION (Methods 1-6)
    # ========================================================================

    def optimize_sharpe_ratio(self, constraints=None):
        """1. Maximize Sharpe Ratio"""
        return self._run_optimization(lambda w: -self.performance_stats(w)[2], constraints)

    def optimize_min_volatility(self, constraints=None):
        """2. Minimize Volatility"""
        return self._run_optimization(lambda w: self.performance_stats(w)[1], constraints)

    def optimize_min_vol_target_return(self, target_return, user_constraints=None):
        """3. Minimize Volatility subject to Target Return"""
        target_return = float(target_return) / 100.0 if target_return else 0.10
        
        def objective(w):
            return self.performance_stats(w)[1]
        
        bounds = self._build_bounds(user_constraints)
        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'ineq', 'fun': lambda x: self.performance_stats(x)[0] - target_return}
        ]
        cons = self._add_group_constraints_to_list(cons)
        
        result = minimize(objective, self._initial_guess(), method='SLSQP', bounds=bounds, constraints=cons)
        return self._format_result(result)
    
    def optimize_max_return_target_vol(self, target_volatility, user_constraints=None):
        """4. Maximize Return subject to Target Volatility"""
        target_volatility = float(target_volatility) / 100.0 if target_volatility else 0.15
        
        def objective(w):
            return -self.performance_stats(w)[0]
        
        bounds = self._build_bounds(user_constraints)
        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'ineq', 'fun': lambda x: target_volatility - self.performance_stats(x)[1]}
        ]
        cons = self._add_group_constraints_to_list(cons)
        
        result = minimize(objective, self._initial_guess(), method='SLSQP', bounds=bounds, constraints=cons)
        return self._format_result(result)
    
    def optimize_risk_parity(self):
        """5. Risk Parity (Equal Risk Contribution)"""
        def risk_parity_objective(w):
            port_vol = np.sqrt(np.dot(w.T, np.dot(self.cov_matrix, w)))
            if port_vol == 0:
                return 1e10
            marginal_contrib = np.dot(self.cov_matrix, w) / port_vol
            risk_contrib = w * marginal_contrib
            target_risk = port_vol / self.num_assets
            return np.sum((risk_contrib - target_risk) ** 2)
        
        bounds = tuple((0.0, 1.0) for _ in range(self.num_assets))
        cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        
        result = minimize(risk_parity_objective, self._initial_guess(), method='SLSQP', bounds=bounds, constraints=cons)
        return self._format_result(result)
    
    def equal_weight_portfolio(self):
        """6. Equal Weight (Baseline)"""
        weights = np.ones(self.num_assets) / self.num_assets
        return self._format_result(self._dummy_result(weights))

    # ========================================================================
    # CVAR OPTIMIZATION (Methods 7-9)
    # ========================================================================

    def optimize_min_cvar(self, constraints=None):
        """7. Minimize Conditional Value-at-Risk"""
        def cvar_objective(w):
            port_daily_rets = self.returns.dot(w)
            var_95 = np.percentile(port_daily_rets, 5)
            cvar = port_daily_rets[port_daily_rets <= var_95].mean()
            return cvar  # Negative (loss), minimize it
        
        return self._run_optimization(cvar_objective, constraints)

    def optimize_min_cvar_target_return(self, target_return, user_constraints=None):
        """8. Minimize CVaR subject to Target Return"""
        target_return = float(target_return) / 100.0 if target_return else 0.10
        
        def cvar_objective(w):
            port_daily_rets = self.returns.dot(w)
            var_95 = np.percentile(port_daily_rets, 5)
            return port_daily_rets[port_daily_rets <= var_95].mean()
        
        bounds = self._build_bounds(user_constraints)
        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'ineq', 'fun': lambda x: self.performance_stats(x)[0] - target_return}
        ]
        cons = self._add_group_constraints_to_list(cons)
        
        result = minimize(cvar_objective, self._initial_guess(), method='SLSQP', bounds=bounds, constraints=cons)
        return self._format_result(result)

    def optimize_max_return_target_cvar(self, target_cvar, user_constraints=None):
        """9. Maximize Return subject to Target CVaR"""
        target_cvar = float(target_cvar) / 100.0 if target_cvar else -0.02
        
        def objective(w):
            return -self.performance_stats(w)[0]
        
        def cvar_constraint(w):
            port_daily_rets = self.returns.dot(w)
            var_95 = np.percentile(port_daily_rets, 5)
            cvar = port_daily_rets[port_daily_rets <= var_95].mean()
            return cvar - target_cvar  # CVaR >= target (less negative)
        
        bounds = self._build_bounds(user_constraints)
        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'ineq', 'fun': cvar_constraint}
        ]
        cons = self._add_group_constraints_to_list(cons)
        
        result = minimize(objective, self._initial_guess(), method='SLSQP', bounds=bounds, constraints=cons)
        return self._format_result(result)

    # ========================================================================
    # TRACKING ERROR OPTIMIZATION (Methods 10-12)
    # ========================================================================

    def optimize_min_tracking_error(self, benchmark_ticker, user_constraints=None):
        """10. Minimize Tracking Error vs Benchmark"""
        if benchmark_ticker not in self.tickers:
            raise ValueError(f"Benchmark {benchmark_ticker} not in portfolio")
        
        bench_idx = self.tickers.index(benchmark_ticker)
        bench_returns = self.returns.iloc[:, bench_idx]
        
        def tracking_error_objective(w):
            port_rets = self.returns.dot(w)
            tracking_diff = port_rets - bench_returns
            return tracking_diff.std() * np.sqrt(self.trading_days)
        
        return self._run_optimization(tracking_error_objective, user_constraints)

    def optimize_max_information_ratio(self, benchmark_ticker, user_constraints=None):
        """11. Maximize Information Ratio"""
        if benchmark_ticker not in self.tickers:
            raise ValueError(f"Benchmark {benchmark_ticker} not in portfolio")
        
        bench_idx = self.tickers.index(benchmark_ticker)
        bench_returns = self.returns.iloc[:, bench_idx]
        
        def information_ratio_objective(w):
            port_rets = self.returns.dot(w)
            excess_rets = port_rets - bench_returns
            excess_return = excess_rets.mean() * self.trading_days
            tracking_error = excess_rets.std() * np.sqrt(self.trading_days)
            ir = excess_return / tracking_error if tracking_error > 0 else 0
            return -ir  # Maximize by minimizing negative
        
        return self._run_optimization(information_ratio_objective, user_constraints)

    def optimize_max_excess_return_target_te(self, benchmark_ticker, target_te, user_constraints=None):
        """12. Maximize Excess Return subject to Target Tracking Error"""
        if benchmark_ticker not in self.tickers:
            raise ValueError(f"Benchmark {benchmark_ticker} not in portfolio")
        
        target_te = float(target_te) / 100.0 if target_te else 0.05
        bench_idx = self.tickers.index(benchmark_ticker)
        bench_returns = self.returns.iloc[:, bench_idx]
        
        def objective(w):
            port_rets = self.returns.dot(w)
            excess_return = (port_rets - bench_returns).mean() * self.trading_days
            return -excess_return
        
        def te_constraint(w):
            port_rets = self.returns.dot(w)
            te = (port_rets - bench_returns).std() * np.sqrt(self.trading_days)
            return target_te - te
        
        bounds = self._build_bounds(user_constraints)
        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'ineq', 'fun': te_constraint}
        ]
        cons = self._add_group_constraints_to_list(cons)
        
        result = minimize(objective, self._initial_guess(), method='SLSQP', bounds=bounds, constraints=cons)
        return self._format_result(result)

    # ========================================================================
    # ADVANCED OPTIMIZATION (Methods 13-16)
    # ========================================================================

    def optimize_kelly_criterion(self, constraints=None):
        """13. Maximize Kelly Criterion (Geometric Mean)"""
        def kelly_objective(w):
            port_rets = self.returns.dot(w)
            geometric_mean = np.exp(np.log(1 + port_rets).mean()) - 1
            return -geometric_mean * self.trading_days
        
        return self._run_optimization(kelly_objective, constraints)

    def optimize_min_drawdown_target_return(self, target_return, user_constraints=None):
        """14. Minimize Maximum Drawdown subject to Target Return"""
        target_return = float(target_return) / 100.0 if target_return else 0.10
        
        def drawdown_objective(w):
            port_rets = self.returns.dot(w)
            cumulative = (1 + port_rets).cumprod()
            peak = cumulative.expanding(min_periods=1).max()
            drawdown = (cumulative / peak) - 1
            return drawdown.min()  # Most negative value
        
        bounds = self._build_bounds(user_constraints)
        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'ineq', 'fun': lambda x: self.performance_stats(x)[0] - target_return}
        ]
        cons = self._add_group_constraints_to_list(cons)
        
        result = minimize(drawdown_objective, self._initial_guess(), method='SLSQP', bounds=bounds, constraints=cons)
        return self._format_result(result)

    def optimize_max_omega_target_return(self, target_return, user_constraints=None):
        """15. Maximize Omega Ratio subject to Target Return"""
        target_return_pct = float(target_return) / 100.0 if target_return else 0.10
        threshold = self.rf_rate / self.trading_days  # Daily threshold
        
        def omega_objective(w):
            port_rets = self.returns.dot(w)
            gains = port_rets[port_rets > threshold] - threshold
            losses = threshold - port_rets[port_rets <= threshold]
            omega = gains.sum() / losses.sum() if losses.sum() > 0 else 0
            return -omega
        
        bounds = self._build_bounds(user_constraints)
        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'ineq', 'fun': lambda x: self.performance_stats(x)[0] - target_return_pct}
        ]
        cons = self._add_group_constraints_to_list(cons)
        
        result = minimize(omega_objective, self._initial_guess(), method='SLSQP', bounds=bounds, constraints=cons)
        return self._format_result(result)

    def optimize_max_sortino_target_return(self, target_return, user_constraints=None):
        """16. Maximize Sortino Ratio subject to Target Return"""
        target_return_pct = float(target_return) / 100.0 if target_return else 0.10
        
        def sortino_objective(w):
            port_rets = self.returns.dot(w)
            expected_return = port_rets.mean() * self.trading_days
            negative_rets = port_rets[port_rets < 0]
            downside_std = negative_rets.std() * np.sqrt(self.trading_days) if len(negative_rets) > 0 else 1e-6
            sortino = (expected_return - self.rf_rate) / downside_std
            return -sortino
        
        bounds = self._build_bounds(user_constraints)
        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'ineq', 'fun': lambda x: self.performance_stats(x)[0] - target_return_pct}
        ]
        cons = self._add_group_constraints_to_list(cons)
        
        result = minimize(sortino_objective, self._initial_guess(), method='SLSQP', bounds=bounds, constraints=cons)
        return self._format_result(result)

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def calculate_portfolio_stats(self, weights):
        """Calculate stats for any given weight vector"""
        weights = np.array(weights)
        ret, vol, sharpe = self.performance_stats(weights)
        adv_stats = self.advanced_stats(weights)
        
        clean_weights = {
            self.tickers[i]: round(weights[i] * 100, 2) 
            for i in range(len(weights)) 
            if weights[i] > 0.001
        }
        
        port_daily_rets = self.returns.dot(weights)
        cumulative = (1 + port_daily_rets).cumprod()
        peak = cumulative.expanding(min_periods=1).max()
        drawdown = (cumulative / peak) - 1

        equity_curve = [{"date": str(d.date()) if hasattr(d, "date") else str(d), "value": val} for d, val in cumulative.items()]
        drawdown_curve = [{"date": str(d.date()) if hasattr(d, "date") else str(d), "value": val} for d, val in drawdown.items()]
        
        output = {
            "weights": clean_weights,
            "return": round(ret * 100, 2),
            "volatility": round(vol * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "equity_curve": equity_curve,
            "drawdown_curve": drawdown_curve
        }
        output.update(adv_stats)
        return output

    def _run_optimization(self, objective_func, user_constraints=None):
        bounds = self._build_bounds(user_constraints)
        cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        cons = self._add_group_constraints_to_list(cons)
        result = minimize(objective_func, self._initial_guess(), method='SLSQP', bounds=bounds, constraints=cons)
        return self._format_result(result)

    def _initial_guess(self):
        return self.num_assets * [1. / self.num_assets,]

    def _build_bounds(self, user_constraints):
        bounds = [(0.0, 1.0) for _ in range(self.num_assets)]
        if user_constraints and 'assets' in user_constraints:
            for i, ticker in enumerate(self.tickers):
                if ticker in user_constraints['assets']:
                    c = user_constraints['assets'][ticker]
                    min_w = max(0.0, float(c.get('min', 0.0)))
                    max_w = min(1.0, float(c.get('max', 1.0)))
                    bounds[i] = (min_w, max_w)
        return tuple(bounds)

    def _dummy_result(self, weights):
        class DummyResult:
            def __init__(self, x):
                self.x = x
        return DummyResult(weights)

    def _format_result(self, result):
        weights = result.x
        ret, vol, sharpe = self.performance_stats(weights)
        adv_stats = self.advanced_stats(weights)
        
        clean_weights = {
            self.tickers[i]: round(weights[i] * 100, 2) 
            for i in range(len(weights)) 
            if weights[i] > 0.001
        }

        port_daily_rets = self.returns.dot(weights)
        cumulative = (1 + port_daily_rets).cumprod()
        peak = cumulative.expanding(min_periods=1).max()
        drawdown = (cumulative / peak) - 1

        equity_curve = [{"date": str(d.date()) if hasattr(d, "date") else str(d), "value": val} for d, val in cumulative.items()]
        drawdown_curve = [{"date": str(d.date()) if hasattr(d, "date") else str(d), "value": val} for d, val in drawdown.items()]
        
        output = {
            "weights": clean_weights,
            "return": round(ret * 100, 2),
            "volatility": round(vol * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "equity_curve": equity_curve,
            "drawdown_curve": drawdown_curve
        }
        
        output.update(adv_stats)
        output["stress_tests"] = self.analyze_stress_periods(weights)
        output["monthly_heatmap"] = self.get_monthly_heatmap(weights)
        output["rolling_returns"] = self.get_rolling_returns(weights)
        
        return output

    def analyze_stress_periods(self, weights):
        stress_events = [
            {"name": "Covid-19", "start": "2020-02-19", "end": "2020-03-23"},
            {"name": "2022 Bear", "start": "2022-01-03", "end": "2022-10-12"},
            {"name": "2018 Correction", "start": "2018-09-20", "end": "2018-12-24"},
            {"name": "2008 Crisis", "start": "2007-10-09", "end": "2009-03-09"}
        ]
        port_daily = self.returns.dot(weights)
        if not isinstance(port_daily.index, pd.DatetimeIndex): 
            port_daily.index = pd.to_datetime(port_daily.index)
        
        results = []
        for event in stress_events:
            start, end = pd.to_datetime(event["start"]), pd.to_datetime(event["end"])
            mask = (port_daily.index >= start) & (port_daily.index <= end)
            period = port_daily.loc[mask]
            if not period.empty:
                ret = (1 + period).prod() - 1
                results.append({"name": event["name"], "start": event["start"], "end": event["end"], "return": round(ret * 100, 2)})
        return results

    def get_monthly_heatmap(self, weights):
        port_daily = self.returns.dot(weights)
        if not isinstance(port_daily.index, pd.DatetimeIndex): 
            port_daily.index = pd.to_datetime(port_daily.index)
        
        monthly = port_daily.resample('M').apply(lambda x: (1 + x).prod() - 1)
        df = pd.DataFrame({'ret': monthly})
        df['year'] = df.index.year
        df['month'] = df.index.month
        pivot = df.pivot(index='year', columns='month', values='ret').sort_index(ascending=False)
        
        years = pivot.index.tolist()
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        z = []
        for y in years:
            row = []
            for m in range(1, 13):
                val = pivot.loc[y, m] if m in pivot.columns else None
                row.append(round(val * 100, 2) if pd.notna(val) else None)
            z.append(row)
            
        return {"years": years, "months": months, "z": z}

    def get_rolling_returns(self, weights):
        port_daily = self.returns.dot(weights)
        if not isinstance(port_daily.index, pd.DatetimeIndex): 
            port_daily.index = pd.to_datetime(port_daily.index)
        monthly = port_daily.resample('M').apply(lambda x: (1 + x).prod() - 1)
        
        rolling_data = {}
        for name, window in {"1 Year": 12, "3 Years": 36}.items():
            if len(monthly) >= window:
                cum = (1 + monthly).rolling(window=window).apply(np.prod, raw=True) - 1
                ann = (1 + cum) ** (12 / window) - 1
                rolling_data[name] = [{"date": str(d.date()), "value": round(v * 100, 2)} for d, v in ann.dropna().items()]
        return rolling_data
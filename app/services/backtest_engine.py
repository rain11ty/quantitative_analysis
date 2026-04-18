# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger
import warnings
warnings.filterwarnings('ignore')

# --- 预留接口（以下模块属于高级量化投研流水线，当前版本未实现）---
# FactorValues / MLPredictions    → 因子值 & ML预测结果 ORM 模型
# FactorEngine                     → 因子计算引擎
# MLModelManager                   → ML模型管理器
# StockScoringEngine               → 综合评分引擎
# PortfolioOptimizer               → 投资组合优化器
# 如需启用高级回测，需先实现上述模块并取消下方注释
from app.models import StockDailyHistory


class BacktestEngine:
    """回测验证引擎（高级版：支持多因子选股 + ML增强 + 组合优化）
    
    注意：当前版本核心回测功能使用 analysis_api.py 内置的简化版 BacktestEngine。
    本类为高级扩展接口，依赖 FactorEngine / MLModelManager / StockScoringEngine /
    PortfolioOptimizer 等尚未实现的模块。待相关模块实现后可启用完整功能。
    """
    
    def __init__(self):
        # 预留属性，高级模块实现后启用
        self.factor_engine = None
        self.ml_manager = None
        self.scoring_engine = None
        self.portfolio_optimizer = None
    
    def _get_factor_engine(self):
        """延迟初始化因子引擎（预留接口）"""
        raise NotImplementedError("FactorEngine 尚未实现，属于高级量化投研流水线预留模块")
    
    def _get_ml_manager(self):
        """延迟初始化ML管理器（预留接口）"""
        raise NotImplementedError("MLModelManager 尚未实现，属于高级量化投研流水线预留模块")
    
    def _get_scoring_engine(self):
        """延迟初始化评分引擎（预留接口）"""
        raise NotImplementedError("StockScoringEngine 尚未实现，属于高级量化投研流水线预留模块")
    
    def _get_portfolio_optimizer(self):
        """延迟初始化投资组合优化器（预留接口）"""
        raise NotImplementedError("PortfolioOptimizer 尚未实现，属于高级量化投研流水线预留模块")
        
    def run_backtest(self, strategy_config: Dict[str, Any], 
                    start_date: str, end_date: str,
                    initial_capital: float = 1000000.0,
                    rebalance_frequency: str = 'monthly') -> Dict[str, Any]:
        """
        运行回测
        
        Args:
            strategy_config: 策略配置
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            rebalance_frequency: 再平衡频率 ('daily', 'weekly', 'monthly')
            
        Returns:
            回测结果
        """
        try:
            logger.info(f"开始回测: {start_date} to {end_date}")
            
            # 生成交易日期
            trade_dates = self._generate_trade_dates(start_date, end_date, rebalance_frequency)
            
            # 初始化回测状态
            portfolio_values = []
            positions = {}
            cash = initial_capital
            total_value = initial_capital
            
            # 记录每日数据
            daily_returns = []
            daily_positions = []
            daily_turnover = []
            
            for i, trade_date in enumerate(trade_dates):
                logger.info(f"处理交易日: {trade_date}")
                
                try:
                    # 获取当日选股结果
                    selected_stocks = self._get_stock_selection(strategy_config, trade_date)
                    
                    if not selected_stocks:
                        logger.warning(f"日期 {trade_date} 没有选出股票")
                        continue
                    
                    # 组合优化
                    target_weights = self._get_target_weights(
                        selected_stocks, strategy_config.get('optimization', {})
                    )
                    
                    # 计算当前持仓价值
                    current_prices = self._get_current_prices(trade_date, list(positions.keys()))
                    current_portfolio_value = self._calculate_portfolio_value(
                        positions, current_prices, cash
                    )
                    
                    # 执行再平衡
                    new_positions, new_cash, turnover = self._rebalance_portfolio(
                        positions, cash, target_weights, current_prices, 
                        current_portfolio_value, strategy_config.get('transaction_cost', 0.001)
                    )
                    
                    # 更新状态
                    positions = new_positions
                    cash = new_cash
                    total_value = current_portfolio_value
                    
                    # 记录数据
                    portfolio_values.append({
                        'date': trade_date,
                        'total_value': total_value,
                        'cash': cash,
                        'positions_value': total_value - cash
                    })
                    
                    daily_positions.append(positions.copy())
                    daily_turnover.append(turnover)
                    
                    # 计算日收益率
                    if i > 0:
                        daily_return = (total_value - portfolio_values[i-1]['total_value']) / portfolio_values[i-1]['total_value']
                        daily_returns.append(daily_return)
                    
                except Exception as e:
                    logger.error(f"处理交易日 {trade_date} 时出错: {e}")
                    continue
            
            # 计算回测指标
            performance_metrics = self._calculate_performance_metrics(
                portfolio_values, daily_returns, start_date, end_date
            )
            
            # 获取基准收益
            benchmark_returns = self._get_benchmark_returns(start_date, end_date)
            
            return {
                'success': True,
                'strategy_config': strategy_config,
                'backtest_period': f"{start_date} to {end_date}",
                'initial_capital': initial_capital,
                'final_value': total_value,
                'total_return': (total_value - initial_capital) / initial_capital,
                'portfolio_values': portfolio_values,
                'daily_returns': daily_returns,
                'daily_positions': daily_positions,
                'daily_turnover': daily_turnover,
                'performance_metrics': performance_metrics,
                'benchmark_returns': benchmark_returns
            }
            
        except Exception as e:
            logger.error(f"回测失败: {e}")
            return {'error': str(e)}
    
    def _generate_trade_dates(self, start_date: str, end_date: str, 
                            frequency: str) -> List[str]:
        """生成交易日期"""
        try:
            # 获取所有交易日
            query = db.session.query(StockDailyHistory.trade_date).distinct()
            query = query.filter(
                StockDailyHistory.trade_date >= start_date,
                StockDailyHistory.trade_date <= end_date
            )
            all_dates = [row[0] for row in query.order_by(StockDailyHistory.trade_date)]
            
            if frequency == 'daily':
                return all_dates
            elif frequency == 'weekly':
                # 每周第一个交易日
                weekly_dates = []
                current_week = None
                for date in all_dates:
                    week = pd.to_datetime(date).isocalendar()[1]
                    if week != current_week:
                        weekly_dates.append(date)
                        current_week = week
                return weekly_dates
            elif frequency == 'monthly':
                # 每月第一个交易日
                monthly_dates = []
                current_month = None
                for date in all_dates:
                    month = pd.to_datetime(date).month
                    if month != current_month:
                        monthly_dates.append(date)
                        current_month = month
                return monthly_dates
            else:
                return all_dates
                
        except Exception as e:
            logger.error(f"生成交易日期失败: {e}")
            return []
    
    def _get_stock_selection(self, strategy_config: Dict[str, Any], 
                           trade_date: str) -> List[Dict[str, Any]]:
        """获取股票选择结果（预留接口，需 StockScoringEngine 实现后可用）"""
        try:
            selection_method = strategy_config.get('selection_method', 'factor_based')
            
            logger.warning(
                f"高级选股方法 '{selection_method}' 当前不可用，"
                f"请使用 analysis_api.py 内置回测引擎（支持 MA/MACD/KDJ/RSI/布林带策略）"
            )
            return []
                
        except Exception as e:
            logger.error(f"获取股票选择结果失败: {e}")
            return []
    
    def _get_target_weights(self, selected_stocks: List[Dict[str, Any]], 
                          optimization_config: Dict[str, Any]) -> Dict[str, float]:
        """获取目标权重（预留接口，需 PortfolioOptimizer 实现后可用非等权优化）"""
        try:
            # 当前仅支持等权重分配
            if not selected_stocks:
                return {}
            weight = 1.0 / len(selected_stocks)
            return {stock['ts_code']: weight for stock in selected_stocks}
                
        except Exception as e:
            logger.error(f"获取目标权重失败: {e}")
            weight = 1.0 / len(selected_stocks) if selected_stocks else 1.0
            return {stock['ts_code']: weight for stock in selected_stocks}
    
    def _get_current_prices(self, trade_date: str, ts_codes: List[str]) -> Dict[str, float]:
        """获取当前价格"""
        try:
            if not ts_codes:
                return {}
            
            query = db.session.query(
                StockDailyHistory.ts_code,
                StockDailyHistory.close
            ).filter(
                StockDailyHistory.trade_date == trade_date,
                StockDailyHistory.ts_code.in_(ts_codes)
            )
            
            return {row[0]: float(row[1]) for row in query}
            
        except Exception as e:
            logger.error(f"获取当前价格失败: {e}")
            return {}
    
    def _calculate_portfolio_value(self, positions: Dict[str, int], 
                                 prices: Dict[str, float], cash: float) -> float:
        """计算组合价值"""
        try:
            positions_value = sum(
                positions.get(ts_code, 0) * prices.get(ts_code, 0)
                for ts_code in positions.keys()
            )
            return positions_value + cash
            
        except Exception as e:
            logger.error(f"计算组合价值失败: {e}")
            return cash
    
    def _rebalance_portfolio(self, current_positions: Dict[str, int], 
                           current_cash: float, target_weights: Dict[str, float],
                           prices: Dict[str, float], total_value: float,
                           transaction_cost: float) -> Tuple[Dict[str, int], float, float]:
        """执行组合再平衡"""
        try:
            new_positions = {}
            turnover = 0.0
            
            # 计算目标持仓
            for ts_code, weight in target_weights.items():
                if ts_code in prices and prices[ts_code] > 0:
                    target_value = total_value * weight
                    target_shares = int(target_value / prices[ts_code] / 100) * 100  # 按手数调整
                    new_positions[ts_code] = target_shares
            
            # 计算交易成本和换手率
            total_trade_value = 0.0
            for ts_code in set(list(current_positions.keys()) + list(new_positions.keys())):
                current_shares = current_positions.get(ts_code, 0)
                new_shares = new_positions.get(ts_code, 0)
                price = prices.get(ts_code, 0)
                
                if price > 0:
                    trade_value = abs(new_shares - current_shares) * price
                    total_trade_value += trade_value
            
            turnover = total_trade_value / total_value if total_value > 0 else 0
            transaction_costs = total_trade_value * transaction_cost
            
            # 计算新的现金余额
            new_cash = current_cash
            for ts_code in set(list(current_positions.keys()) + list(new_positions.keys())):
                current_shares = current_positions.get(ts_code, 0)
                new_shares = new_positions.get(ts_code, 0)
                price = prices.get(ts_code, 0)
                
                if price > 0:
                    trade_value = (new_shares - current_shares) * price
                    new_cash -= trade_value
            
            new_cash -= transaction_costs
            
            return new_positions, new_cash, turnover
            
        except Exception as e:
            logger.error(f"组合再平衡失败: {e}")
            return current_positions, current_cash, 0.0
    
    def _calculate_performance_metrics(self, portfolio_values: List[Dict[str, Any]], 
                                     daily_returns: List[float],
                                     start_date: str, end_date: str) -> Dict[str, Any]:
        """计算回测指标"""
        try:
            if not portfolio_values or not daily_returns:
                return {}
            
            # 基本指标
            initial_value = portfolio_values[0]['total_value']
            final_value = portfolio_values[-1]['total_value']
            total_return = (final_value - initial_value) / initial_value
            
            # 年化收益率
            days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days
            years = days / 365.25
            annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
            
            # 波动率
            returns_array = np.array(daily_returns)
            volatility = np.std(returns_array) * np.sqrt(252)  # 年化波动率
            
            # 夏普比率 (假设无风险利率为3%)
            risk_free_rate = 0.03
            sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0
            
            # 最大回撤
            values = [pv['total_value'] for pv in portfolio_values]
            peak = values[0]
            max_drawdown = 0
            for value in values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            # 胜率
            positive_returns = [r for r in daily_returns if r > 0]
            win_rate = len(positive_returns) / len(daily_returns) if daily_returns else 0
            
            # 卡尔玛比率
            calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0
            
            return {
                'total_return': total_return,
                'annualized_return': annualized_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'win_rate': win_rate,
                'calmar_ratio': calmar_ratio,
                'total_trades': len(daily_returns),
                'avg_daily_return': np.mean(daily_returns) if daily_returns else 0,
                'std_daily_return': np.std(daily_returns) if daily_returns else 0
            }
            
        except Exception as e:
            logger.error(f"计算回测指标失败: {e}")
            return {}
    
    def _get_benchmark_returns(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """获取基准收益率（沪深300指数 / 买入持有基准）
        
        从 stock_daily_history 表查询指数日线数据，计算日收益率序列。
        支持的基准代码：000300.SH（沪深300）、000001.SH（上证指数）、399001.SZ（深证成指）
        
        Args:
            start_date: 回测起始日期
            end_date: 回测结束日期
            
        Returns:
            基准日收益率列表 [{'date': '2024-01-02', 'return': 0.005}, ...]
        """
        try:
            benchmark_code = '000300.SH'  # 默认使用沪深300指数作为基准
            
            # 查询基准指数在回测期间内的日线数据
            query = db.session.query(
                StockDailyHistory.trade_date,
                StockDailyHistory.close,
                StockDailyHistory.pct_chg
            ).filter(
                StockDailyHistory.ts_code == benchmark_code,
                StockDailyHistory.trade_date >= start_date,
                StockDailyHistory.trade_date <= end_date
            ).order_by(StockDailyHistory.trade_date)
            
            records = query.all()
            
            if not records:
                logger.warning(f"未找到基准指数 {benchmark_code} 在 {start_date} ~ {end_date} 的数据")
                return []
            
            # 构建日期-收益率序列（pct_chg 字段为涨跌幅百分比，需除以100）
            benchmark_returns = []
            for row in records:
                pct_change = float(row.pct_chg) if row.pct_chg is not None else 0.0
                benchmark_returns.append({
                    'date': str(row.trade_date),
                    'close': float(row.close),
                    'return': pct_change / 100.0  # 百分比转小数
                })
            
            logger.info(
                f"获取到 {benchmark_code} 基准数据 {len(benchmark_returns)} 条 "
                f"({start_date} ~ {end_date})"
            )
            return benchmark_returns
            
        except Exception as e:
            logger.error(f"获取基准收益率失败: {e}")
            return []
    
    def compare_strategies(self, strategies: List[Dict[str, Any]], 
                         start_date: str, end_date: str) -> Dict[str, Any]:
        """比较多个策略"""
        try:
            results = []
            
            for i, strategy in enumerate(strategies):
                logger.info(f"回测策略 {i+1}: {strategy.get('name', f'Strategy_{i+1}')}")
                
                result = self.run_backtest(
                    strategy['config'], start_date, end_date,
                    strategy.get('initial_capital', 1000000.0),
                    strategy.get('rebalance_frequency', 'monthly')
                )
                
                if result.get('success'):
                    results.append({
                        'strategy_name': strategy.get('name', f'Strategy_{i+1}'),
                        'result': result
                    })
            
            # 生成比较报告
            comparison = self._generate_comparison_report(results)
            
            return {
                'success': True,
                'strategies': results,
                'comparison': comparison
            }
            
        except Exception as e:
            logger.error(f"策略比较失败: {e}")
            return {'error': str(e)}
    
    def _generate_comparison_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成策略比较报告"""
        try:
            if not results:
                return {}
            
            comparison_metrics = {}
            
            for result in results:
                strategy_name = result['strategy_name']
                metrics = result['result']['performance_metrics']
                
                comparison_metrics[strategy_name] = {
                    'total_return': metrics.get('total_return', 0),
                    'annualized_return': metrics.get('annualized_return', 0),
                    'volatility': metrics.get('volatility', 0),
                    'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                    'max_drawdown': metrics.get('max_drawdown', 0),
                    'win_rate': metrics.get('win_rate', 0),
                    'calmar_ratio': metrics.get('calmar_ratio', 0)
                }
            
            # 找出最佳策略
            best_strategy = {
                'highest_return': max(comparison_metrics.items(), 
                                    key=lambda x: x[1]['total_return'])[0],
                'highest_sharpe': max(comparison_metrics.items(), 
                                    key=lambda x: x[1]['sharpe_ratio'])[0],
                'lowest_drawdown': min(comparison_metrics.items(), 
                                     key=lambda x: x[1]['max_drawdown'])[0],
                'highest_win_rate': max(comparison_metrics.items(), 
                                      key=lambda x: x[1]['win_rate'])[0]
            }
            
            return {
                'metrics_comparison': comparison_metrics,
                'best_strategy': best_strategy,
                'summary': {
                    'total_strategies': len(results),
                    'avg_return': np.mean([m['total_return'] for m in comparison_metrics.values()]),
                    'avg_sharpe': np.mean([m['sharpe_ratio'] for m in comparison_metrics.values()]),
                    'avg_drawdown': np.mean([m['max_drawdown'] for m in comparison_metrics.values()])
                }
            }
            
        except Exception as e:
            logger.error(f"生成比较报告失败: {e}")
            return {} 
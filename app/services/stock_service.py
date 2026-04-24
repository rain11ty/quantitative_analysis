# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from typing import List, Dict, Optional

from sqlalchemy import and_, asc, desc, or_

from app.extensions import db
from app.models import (
    StockBasic, StockDailyHistory, StockDailyBasic,
    StockFactor, StockMaData, StockMoneyflow, StockCyqPerf
)
from loguru import logger
import pandas as pd
import numpy as np
from app.utils.cache_utils import cache as _cache


class StockService:
    """股票数据服务类"""
    
    # 动态查询字段白名单：仅允许在 screen_stocks 动态条件中使用的 StockBusiness 字段
    # 防止用户传入恶意字段名导致非预期数据访问
    _SCREEN_ALLOWED_FIELDS = frozenset({
        # 估值指标
        'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 'dv_ratio', 'dv_ttm',
        # 市值指标
        'total_mv', 'circ_mv', 'total_share', 'float_share', 'free_share',
        # 交易指标
        'turnover_rate', 'turnover_rate_f', 'volume_ratio',
        # 技术因子
        'factor_macd_dif', 'factor_macd_dea', 'factor_macd',
        'factor_kdj_k', 'factor_kdj_d', 'factor_kdj_j',
        'factor_rsi_6', 'factor_rsi_12', 'factor_rsi_24',
        'factor_cci', 'factor_boll_upper', 'factor_boll_mid', 'factor_boll_lower',
        # 资金流向
        'moneyflow_net_amount', 'moneyflow_net_d5_amount',
        'moneyflow_buy_lg_amount_rate', 'moneyflow_buy_md_amount_rate', 'moneyflow_buy_sm_amount_rate',
        # 均线
        'ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120',
        # 价格/涨跌
        'daily_close', 'factor_open', 'factor_high', 'factor_low', 'factor_pct_change',
    })
    
    @staticmethod
    def get_stock_list(industry=None, area=None, search=None, page=1, page_size=20):
        """获取股票列表，支持代码、简称与拼音检索。"""
        try:
            query = StockBasic.query

            if industry:
                query = query.filter(StockBasic.industry == industry)
            if area:
                query = query.filter(StockBasic.area == area)

            offset = max(page - 1, 0) * page_size

            if search:
                keyword = (search or '').strip()
                if StockService._needs_pinyin_match(keyword):
                    # === 拼音搜索优化：先尝试 SQL 前缀匹配，再内存过滤 ===
                    # 策略1：如果关键词是纯字母，先尝试用 symbol 前缀匹配（SQL索引命中）
                    sql_matches = query.filter(
                        StockBasic.symbol.ilike(f'{keyword}%')
                    ).order_by(asc(StockBasic.symbol)).limit(page_size * 3).all()  # 多取一些做二次过滤
                    
                    matched_stocks = [stock for stock in sql_matches if StockService._matches_stock_search(stock, keyword)]
                    
                    # 如果SQL前缀匹配结果不足，再回退到全表扫描（仅取需要的数据量）
                    if len(matched_stocks) < page_size:
                        all_stocks = query.order_by(asc(StockBasic.symbol)).all()
                        seen_codes = {s.ts_code for s in matched_stocks}
                        for stock in all_stocks:
                            if stock.ts_code not in seen_codes and StockService._matches_stock_search(stock, keyword):
                                matched_stocks.append(stock)
                                seen_codes.add(stock.ts_code)
                                if len(matched_stocks) >= page_size * 2:
                                    break
                    
                    total = len(matched_stocks)  # 注意：全量总数在此模式下可能不精确（性能换准确）
                    page_stocks = matched_stocks[offset: offset + page_size]
                    return {
                        'stocks': [stock.to_dict() for stock in page_stocks],
                        'total': total,
                        'page': page,
                        'page_size': page_size,
                        'total_pages': (total + page_size - 1) // page_size if total else 0,
                    }

                query = query.filter(
                    or_(
                        StockBasic.ts_code.ilike(f'%{keyword}%'),
                        StockBasic.symbol.ilike(f'%{keyword}%'),
                        StockBasic.name.ilike(f'%{keyword}%'),
                    )
                )

            total = query.count()
            stocks = query.order_by(asc(StockBasic.symbol)).offset(offset).limit(page_size).all()

            return {
                'stocks': [stock.to_dict() for stock in stocks],
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size if total else 0,
            }
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return {'stocks': [], 'total': 0, 'page': page, 'page_size': page_size, 'total_pages': 0}

    @staticmethod
    def _normalize_search_keyword(keyword: str) -> str:
        return re.sub(r'[^0-9a-zA-Z\u4e00-\u9fa5]+', '', (keyword or '').strip()).lower()

    @staticmethod
    def _needs_pinyin_match(keyword: str) -> bool:
        normalized = StockService._normalize_search_keyword(keyword)
        return bool(normalized) and any('a' <= char <= 'z' for char in normalized)

    @staticmethod
    def _get_name_pinyin_candidates(name: str):
        try:
            from pypinyin import lazy_pinyin
        except ImportError:
            return []

        syllables = lazy_pinyin(name or '', errors='ignore')
        if not syllables:
            return []

        full_spell = ''.join(syllables)
        initials = ''.join(item[0] for item in syllables if item)
        return [full_spell, initials]

    @staticmethod
    def _matches_stock_search(stock: StockBasic, keyword: str) -> bool:
        normalized_keyword = StockService._normalize_search_keyword(keyword)
        if not normalized_keyword:
            return True

        candidates = [
            stock.ts_code,
            stock.symbol,
            stock.name,
            *StockService._get_name_pinyin_candidates(stock.name),
        ]
        normalized_candidates = [
            StockService._normalize_search_keyword(candidate)
            for candidate in candidates
            if candidate
        ]
        return any(normalized_keyword in candidate for candidate in normalized_candidates)

    @staticmethod
    def get_stock_info(ts_code: str):

        """获取股票基本信息"""
        try:
            stock = StockBasic.query.filter_by(ts_code=ts_code).first()
            return stock.to_dict() if stock else None
        except Exception as e:
            logger.error(f"获取股票信息失败: {ts_code}, 错误: {e}")
            return None
    
    @staticmethod
    def get_daily_history(ts_code: str, start_date: str = None, end_date: str = None, limit: int = 60):
        """获取股票日线历史数据（带2分钟缓存）"""
        try:
            cache_key = f'daily_history_{ts_code}_{start_date}_{end_date}_{limit}'
            cached = _cache.get(cache_key)
            if cached is not None:
                return cached

            query = StockDailyHistory.query.filter_by(ts_code=ts_code)
            
            if start_date:
                query = query.filter(StockDailyHistory.trade_date >= start_date)
            if end_date:
                query = query.filter(StockDailyHistory.trade_date <= end_date)
            
            # 按日期倒序排列，获取最新的数据（最新的在前面）
            history = query.order_by(desc(StockDailyHistory.trade_date)).limit(limit).all()
            
            result = [item.to_dict() for item in history]
            _cache.set(cache_key, result, ttl=120)
            return result
        except Exception as e:
            logger.error(f"获取日线历史数据失败: {ts_code}, 错误: {e}")
            return []
    
    @staticmethod
    def get_daily_basic(ts_code: str, trade_date: str = None):
        """获取股票日线基本数据"""
        try:
            query = StockDailyBasic.query.filter_by(ts_code=ts_code)
            
            if trade_date:
                query = query.filter_by(trade_date=trade_date)
            else:
                # 获取最新数据
                query = query.order_by(desc(StockDailyBasic.trade_date))
            
            basic = query.first()
            return basic.to_dict() if basic else None
        except Exception as e:
            logger.error(f"获取日线基本数据失败: {ts_code}, 错误: {e}")
            return None
    
    @staticmethod
    def get_stock_factors(ts_code: str, start_date: str = None, end_date: str = None, limit: int = 60):
        """获取股票技术因子数据（带5分钟缓存）"""
        try:
            # 构建缓存键
            cache_key = f'stock_factors_{ts_code}_{start_date}_{end_date}_{limit}'
            cached = _cache.get(cache_key)
            if cached is not None:
                return cached

            # 首先尝试从stock_factor表获取数据
            query = StockFactor.query.filter_by(ts_code=ts_code)
            
            if start_date:
                query = query.filter(StockFactor.trade_date >= start_date)
            if end_date:
                query = query.filter(StockFactor.trade_date <= end_date)
            
            # 按日期倒序排列，获取最新的数据（最新的在前面）
            factors = query.order_by(desc(StockFactor.trade_date)).limit(limit).all()
            
            factor_data = [item.to_dict() for item in factors]
            
            # 检查因子数据是否有效：技术指标字段是否为空
            # 如果数据条数不足，或者关键指标字段全为 None，则回退到计算
            needs_calculation = len(factor_data) < limit
            if not needs_calculation and factor_data:
                # 检查最近一条数据的关键指标是否为空
                sample = factor_data[0]
                key_indicators = ['macd_dif', 'macd_dea', 'macd', 'kdj_k', 'kdj_d', 'rsi_6']
                if all(sample.get(k) is None for k in key_indicators):
                    needs_calculation = True
                    logger.info(f"stock_factor表数据指标全为空，回退到基于历史数据计算: {ts_code}")
            
            if needs_calculation:
                logger.info(f"基于历史数据计算技术指标: {ts_code} (表数据不足或无效)")
                history_data = StockService.get_daily_history(ts_code, start_date, end_date, max(limit, 120))
                if history_data:
                    calculated_factors = StockService._calculate_technical_indicators(history_data)
                    if calculated_factors:
                        _cache.set(cache_key, calculated_factors, ttl=300)
                        return calculated_factors
            
            _cache.set(cache_key, factor_data, ttl=300)
            return factor_data
        except Exception as e:
            logger.error(f"获取技术因子数据失败: {ts_code}, 错误: {e}")
            # 如果出错，尝试基于历史数据计算
            try:
                history_data = StockService.get_daily_history(ts_code, start_date, end_date, max(limit, 120))
                if history_data:
                    return StockService._calculate_technical_indicators(history_data)
            except Exception as calc_error:
                logger.error(f"计算技术指标失败: {calc_error}")
            return []
    
    @staticmethod
    def get_ma_data(ts_code: str):
        """获取股票均线数据"""
        try:
            ma_data = StockMaData.query.filter_by(ts_code=ts_code).first()
            return ma_data.to_dict() if ma_data else None
        except Exception as e:
            logger.error(f"获取均线数据失败: {ts_code}, 错误: {e}")
            return None
    
    @staticmethod
    def get_moneyflow(ts_code: str, start_date: str = None, end_date: str = None, limit: int = 30):
        """获取股票资金流向数据"""
        try:
            query = StockMoneyflow.query.filter_by(ts_code=ts_code)
            
            if start_date:
                query = query.filter(StockMoneyflow.trade_date >= start_date)
            if end_date:
                query = query.filter(StockMoneyflow.trade_date <= end_date)
            
            moneyflow = query.order_by(desc(StockMoneyflow.trade_date)).limit(limit).all()
            return [item.to_dict() for item in reversed(moneyflow)]
        except Exception as e:
            logger.error(f"获取资金流向数据失败: {ts_code}, 错误: {e}")
            return []
    
    @staticmethod
    def get_cyq_perf(ts_code: str, start_date: str = None, end_date: str = None, limit: int = 30):
        """获取股票筹码分布数据"""
        try:
            query = StockCyqPerf.query.filter_by(ts_code=ts_code)
            
            if start_date:
                query = query.filter(StockCyqPerf.trade_date >= start_date)
            if end_date:
                query = query.filter(StockCyqPerf.trade_date <= end_date)
            
            cyq_perf = query.order_by(desc(StockCyqPerf.trade_date)).limit(limit).all()
            return [item.to_dict() for item in reversed(cyq_perf)]
        except Exception as e:
            logger.error(f"获取筹码分布数据失败: {ts_code}, 错误: {e}")
            return []
    
    @staticmethod
    def get_stock_detail(ts_code: str):
        """获取股票详细信息（综合数据）"""
        try:
            # 获取基本信息
            basic_info = StockService.get_stock_info(ts_code)
            if not basic_info:
                return None
            
            # 获取最新日线数据
            latest_daily = StockService.get_daily_basic(ts_code)
            
            # 获取均线数据
            ma_data = StockService.get_ma_data(ts_code)
            
            # 获取最近的资金流向
            recent_moneyflow = StockService.get_moneyflow(ts_code, limit=1)
            
            # 获取最近的筹码数据
            recent_cyq = StockService.get_cyq_perf(ts_code, limit=1)
            
            return {
                'basic_info': basic_info,
                'latest_daily': latest_daily,
                'ma_data': ma_data,
                'recent_moneyflow': recent_moneyflow[0] if recent_moneyflow else None,
                'recent_cyq': recent_cyq[0] if recent_cyq else None
            }
        except Exception as e:
            logger.error(f"获取股票详细信息失败: {ts_code}, 错误: {e}")
            return None
    
    @staticmethod
    def get_industry_list():
        """获取行业列表"""
        try:
            industries = db.session.query(StockBasic.industry).distinct().filter(
                StockBasic.industry.isnot(None)
            ).all()
            return [industry[0] for industry in industries if industry[0]]
        except Exception as e:
            logger.error(f"获取行业列表失败: {e}")
            return []
    
    @staticmethod
    def get_area_list():
        """获取地域列表"""
        try:
            areas = db.session.query(StockBasic.area).distinct().filter(
                StockBasic.area.isnot(None)
            ).all()
            return [area[0] for area in areas if area[0]]
        except Exception as e:
            logger.error(f"获取地域列表失败: {e}")
            return []
    
    @staticmethod
    def screen_stocks(criteria: Dict):
        """基于股票业务大宽表的增强筛选"""
        try:
            from app.models import StockBusiness
            from sqlalchemy import and_, or_, text
            from datetime import datetime, timedelta
            
            # 构建基础查询，关联stock_basic表获取行业和地域信息
            query = db.session.query(StockBusiness, StockBasic).join(
                StockBasic, StockBusiness.ts_code == StockBasic.ts_code
            )
            
            # 确定查询日期
            target_date = None
            if criteria.get('trade_date'):
                target_date = datetime.strptime(criteria['trade_date'], '%Y-%m-%d').date()
                query = query.filter(StockBusiness.trade_date == target_date)
            else:
                # 使用最新数据，先获取最新日期
                latest_date = db.session.query(db.func.max(StockBusiness.trade_date)).scalar()
                if latest_date:
                    query = query.filter(StockBusiness.trade_date == latest_date)
            
            # 基本条件筛选
            if criteria.get('industry'):
                query = query.filter(StockBasic.industry == criteria['industry'])
            
            if criteria.get('area'):
                query = query.filter(StockBasic.area == criteria['area'])
            
            if criteria.get('market'):
                market = criteria['market']
                if market == 'SZ':
                    query = query.filter(StockBusiness.ts_code.like('%.SZ'))
                elif market == 'SH':
                    query = query.filter(StockBusiness.ts_code.like('%.SH'))
                elif market == 'BJ':
                    query = query.filter(StockBusiness.ts_code.like('%.BJ'))

            
            # 估值指标筛选
            if criteria.get('pe_min'):
                query = query.filter(StockBusiness.pe >= float(criteria['pe_min']))
            if criteria.get('pe_max'):
                query = query.filter(StockBusiness.pe <= float(criteria['pe_max']))
            
            if criteria.get('pb_min'):
                query = query.filter(StockBusiness.pb >= float(criteria['pb_min']))
            if criteria.get('pb_max'):
                query = query.filter(StockBusiness.pb <= float(criteria['pb_max']))
            
            if criteria.get('ps_min'):
                query = query.filter(StockBusiness.ps >= float(criteria['ps_min']))
            if criteria.get('ps_max'):
                query = query.filter(StockBusiness.ps <= float(criteria['ps_max']))
            
            if criteria.get('dv_min'):
                query = query.filter(StockBusiness.dv_ratio >= float(criteria['dv_min']))
            if criteria.get('dv_max'):
                query = query.filter(StockBusiness.dv_ratio <= float(criteria['dv_max']))
            
            # 市值和交易指标筛选
            if criteria.get('mv_min'):
                query = query.filter(StockBusiness.total_mv >= float(criteria['mv_min']))
            if criteria.get('mv_max'):
                query = query.filter(StockBusiness.total_mv <= float(criteria['mv_max']))
            
            if criteria.get('circ_mv_min'):
                query = query.filter(StockBusiness.circ_mv >= float(criteria['circ_mv_min']))
            if criteria.get('circ_mv_max'):
                query = query.filter(StockBusiness.circ_mv <= float(criteria['circ_mv_max']))
            
            if criteria.get('turnover_min'):
                query = query.filter(StockBusiness.turnover_rate >= float(criteria['turnover_min']))
            if criteria.get('turnover_max'):
                query = query.filter(StockBusiness.turnover_rate <= float(criteria['turnover_max']))
            
            if criteria.get('volume_ratio_min'):
                query = query.filter(StockBusiness.volume_ratio >= float(criteria['volume_ratio_min']))
            if criteria.get('volume_ratio_max'):
                query = query.filter(StockBusiness.volume_ratio <= float(criteria['volume_ratio_max']))
            
            # 技术指标筛选
            if criteria.get('rsi6_min'):
                query = query.filter(StockBusiness.factor_rsi_6 >= float(criteria['rsi6_min']))
            if criteria.get('rsi6_max'):
                query = query.filter(StockBusiness.factor_rsi_6 <= float(criteria['rsi6_max']))
            
            if criteria.get('kdj_k_min'):
                query = query.filter(StockBusiness.factor_kdj_k >= float(criteria['kdj_k_min']))
            if criteria.get('kdj_k_max'):
                query = query.filter(StockBusiness.factor_kdj_k <= float(criteria['kdj_k_max']))
            
            if criteria.get('macd_min'):
                query = query.filter(StockBusiness.factor_macd >= float(criteria['macd_min']))
            if criteria.get('macd_max'):
                query = query.filter(StockBusiness.factor_macd <= float(criteria['macd_max']))
            
            if criteria.get('cci_min'):
                query = query.filter(StockBusiness.factor_cci >= float(criteria['cci_min']))
            if criteria.get('cci_max'):
                query = query.filter(StockBusiness.factor_cci <= float(criteria['cci_max']))
            
            # 资金流向筛选
            if criteria.get('net_amount_min'):
                query = query.filter(StockBusiness.moneyflow_net_amount >= float(criteria['net_amount_min']))
            if criteria.get('net_amount_max'):
                query = query.filter(StockBusiness.moneyflow_net_amount <= float(criteria['net_amount_max']))
            
            if criteria.get('lg_buy_rate_min'):
                query = query.filter(StockBusiness.moneyflow_buy_lg_amount_rate >= float(criteria['lg_buy_rate_min']))
            if criteria.get('lg_buy_rate_max'):
                query = query.filter(StockBusiness.moneyflow_buy_lg_amount_rate <= float(criteria['lg_buy_rate_max']))
            
            if criteria.get('net_d5_amount_min'):
                query = query.filter(StockBusiness.moneyflow_net_d5_amount >= float(criteria['net_d5_amount_min']))
            if criteria.get('net_d5_amount_max'):
                query = query.filter(StockBusiness.moneyflow_net_d5_amount <= float(criteria['net_d5_amount_max']))
            
            # 处理动态查询条件
            dynamic_conditions = criteria.get('dynamic_conditions', [])
            for condition in dynamic_conditions:
                field_a = condition.get('field_a')
                operator = condition.get('operator')
                field_b = condition.get('field_b')
                value = condition.get('value')
                
                if not field_a or not operator:
                    continue
                
                # === 安全校验：字段白名单 ===
                # field_a 必须在允许列表中
                if field_a not in StockService._SCREEN_ALLOWED_FIELDS:
                    logger.warning(f"screen_stocks 动态条件字段被拒绝(不在白名单): field_a={field_a}")
                    continue
                # 如果是字段间比较，field_b 也必须在白名单中
                if field_b and field_b not in StockService._SCREEN_ALLOWED_FIELDS:
                    logger.warning(f"screen_stocks 动态条件字段被拒绝(不在白名单): field_b={field_b}")
                    continue
                
                # 构建动态条件
                if field_b:
                    # 字段间比较
                    field_a_attr = getattr(StockBusiness, field_a, None)
                    field_b_attr = getattr(StockBusiness, field_b, None)
                    
                    if field_a_attr is not None and field_b_attr is not None:
                        if operator == '>':
                            query = query.filter(field_a_attr > field_b_attr)
                        elif operator == '>=':
                            query = query.filter(field_a_attr >= field_b_attr)
                        elif operator == '<':
                            query = query.filter(field_a_attr < field_b_attr)
                        elif operator == '<=':
                            query = query.filter(field_a_attr <= field_b_attr)
                        elif operator == '=':
                            query = query.filter(field_a_attr == field_b_attr)
                        elif operator == '!=':
                            query = query.filter(field_a_attr != field_b_attr)
                elif value is not None:
                    # 字段与固定值比较
                    field_a_attr = getattr(StockBusiness, field_a, None)
                    
                    if field_a_attr is not None:
                        try:
                            value_float = float(value)
                            if operator == '>':
                                query = query.filter(field_a_attr > value_float)
                            elif operator == '>=':
                                query = query.filter(field_a_attr >= value_float)
                            elif operator == '<':
                                query = query.filter(field_a_attr < value_float)
                            elif operator == '<=':
                                query = query.filter(field_a_attr <= value_float)
                            elif operator == '=':
                                query = query.filter(field_a_attr == value_float)
                            elif operator == '!=':
                                query = query.filter(field_a_attr != value_float)
                        except ValueError:
                            logger.warning(f"动态条件值转换失败: {value}")
                            continue
            
            # 分页参数
            page = criteria.get('page', 1)
            page_size = min(criteria.get('page_size', 50), 200)  # 单次最多200条
            
            # 执行查询（先取总数，再分页）
            from sqlalchemy import func
            count_query = db.session.query(func.count()).select_from(query.subquery())
            total_count = count_query.scalar()
            
            offset_val = max(page - 1, 0) * page_size
            results = query.offset(offset_val).limit(page_size).all()
            
            # 转换为字典列表，合并StockBusiness和StockBasic的数据
            stocks = []
            for stock_business, stock_basic in results:
                stock_dict = stock_business.to_dict()
                # 添加基本信息
                stock_dict.update({
                    'industry': stock_basic.industry,
                    'area': stock_basic.area,
                    'symbol': stock_basic.symbol,
                    'name': stock_basic.name,
                    'list_date': stock_basic.list_date.strftime('%Y-%m-%d') if stock_basic.list_date else None
                })
                stocks.append(stock_dict)
            
            logger.info(f"股票筛选完成，共找到 {total_count} 只股票（第{page}页，每页{page_size}条）")
            
            return {
                'stocks': stocks,
                'total': total_count,
                'criteria': criteria,
                'has_more': (offset_val + page_size) < total_count,
                'page': page,
                'page_size': page_size
            }
            
        except Exception as e:
            logger.error(f"股票筛选失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return {
                'stocks': [],
                'total': 0,
                'criteria': criteria,
                'error': str(e)
            }
    
    @staticmethod
    def _calculate_technical_indicators(history_data: List[Dict]) -> List[Dict]:
        """基于历史数据计算技术指标（向量化优化版，O(n) 复杂度）"""
        try:
            import pandas as pd
            import numpy as np
            
            if not history_data or len(history_data) < 20:
                logger.warning("历史数据不足，无法计算技术指标")
                return []
            
            # 转换为DataFrame并按日期排序
            df = pd.DataFrame(history_data)
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values('trade_date').reset_index(drop=True)
            
            close = pd.Series(df['close'], dtype=float)
            high = pd.Series(df['high'], dtype=float)
            low = pd.Series(df['low'], dtype=float)
            
            # ========== 向量化计算所有指标（一次性完成）==========
            
            # --- MACD ---
            ema_fast = close.ewm(span=12).mean()
            ema_slow = close.ewm(span=26).mean()
            macd_dif = (ema_fast - ema_slow)
            macd_dea = macd_dif.ewm(span=9).mean()
            macd_val = (macd_dif - macd_dea) * 2
            
            # --- KDJ ---
            low_min_n = low.rolling(window=9).min()
            high_max_n = high.rolling(window=9).max()
            rsv = (close - low_min_n) / (high_max_n - low_min_n.replace(0, np.nan)) * 100
            kdj_k = rsv.ewm(alpha=1/3).mean()
            kdj_d = kdj_k.ewm(alpha=1/3).mean()
            kdj_j = 3 * kdj_k - 2 * kdj_d
            
            # --- RSI(6, 12, 24) ---
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta.where(delta < 0, 0.0))
            
            def calc_rsi(series, period):
                avg_gain = gain.rolling(window=period).mean()
                avg_loss = loss.rolling(window=period).mean()
                rs = avg_gain / avg_loss.replace(0, np.nan)
                return 100 - (100 / (1 + rs))
            
            rsi_6 = calc_rsi(close, 6)
            rsi_12 = calc_rsi(close, 12)
            rsi_24 = calc_rsi(close, 24)
            
            # --- 布林带 ---
            boll_mid = close.rolling(window=20).mean()
            boll_std = close.rolling(window=20).std()
            boll_upper = boll_mid + (boll_std * 2)
            boll_lower = boll_mid - (boll_std * 2)
            
            # --- CCI ---
            tp = (high + low + close) / 3
            ma_tp = tp.rolling(window=14).mean()
            md_tp = tp.rolling(window=14).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
            cci = (tp - ma_tp) / (0.015 * md_tp.replace(0, np.nan))
            
            # --- 组装结果 ---
            result = []
            for i in range(len(df)):
                if i < 12:  # 前12天数据不足，跳过
                    continue
                    
                row = df.iloc[i]
                factor_data = {
                    'ts_code': str(row['ts_code']),
                    'trade_date': row['trade_date'].strftime('%Y-%m-%d'),
                    'close': float(row['close']) if pd.notna(row['close']) else None,
                    'open': float(row['open']) if pd.notna(row['open']) else None,
                    'high': float(row['high']) if pd.notna(row['high']) else None,
                    'low': float(row['low']) if pd.notna(row['low']) else None,
                    'vol': float(row['vol']) if pd.notna(row['vol']) else None,
                    'amount': float(row['amount']) if pd.notna(row['amount']) else None,
                }
                
                # 直接取预计算好的向量结果
                factor_data['macd_dif'] = round(float(macd_dif.iloc[i]) if not pd.isna(macd_dif.iloc[i]) else 0, 4)
                factor_data['macd_dea'] = round(float(macd_dea.iloc[i]) if not pd.isna(macd_dea.iloc[i]) else 0, 4)
                factor_data['macd'] = round(float(macd_val.iloc[i]) if not pd.isna(macd_val.iloc[i]) else 0, 4)
                
                factor_data['kdj_k'] = round(float(kdj_k.iloc[i]) if not pd.isna(kdj_k.iloc[i]) else 0, 2)
                factor_data['kdj_d'] = round(float(kdj_d.iloc[i]) if not pd.isna(kdj_d.iloc[i]) else 0, 2)
                factor_data['kdj_j'] = round(float(kdj_j.iloc[i]) if not pd.isna(kdj_j.iloc[i]) else 0, 2)
                
                factor_data['rsi_6'] = round(float(rsi_6.iloc[i]) if not pd.isna(rsi_6.iloc[i]) else 0, 2)
                factor_data['rsi_12'] = round(float(rsi_12.iloc[i]) if not pd.isna(rsi_12.iloc[i]) else 0, 2)
                factor_data['rsi_24'] = round(float(rsi_24.iloc[i]) if not pd.isna(rsi_24.iloc[i]) else 0, 2)
                
                factor_data['boll_upper'] = round(float(boll_upper.iloc[i]) if not pd.isna(boll_upper.iloc[i]) else 0, 2)
                factor_data['boll_mid'] = round(float(boll_mid.iloc[i]) if not pd.isna(boll_mid.iloc[i]) else 0, 2)
                factor_data['boll_lower'] = round(float(boll_lower.iloc[i]) if not pd.isna(boll_lower.iloc[i]) else 0, 2)
                
                factor_data['cci'] = round(float(cci.iloc[i]) if not pd.isna(cci.iloc[i]) else 0, 2)
                
                result.append(factor_data)
            
            return result
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            return []
    
    @staticmethod
    def _calculate_macd(prices, fast=12, slow=26, signal=9):
        """计算MACD指标"""
        try:
            import pandas as pd
            
            prices = pd.Series(prices)
            
            # 计算EMA
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            
            # 计算DIF和DEA
            dif = ema_fast - ema_slow
            dea = dif.ewm(span=signal).mean()
            macd = (dif - dea) * 2
            
            return {
                'macd_dif': round(float(dif.iloc[-1]), 4) if not pd.isna(dif.iloc[-1]) else 0,
                'macd_dea': round(float(dea.iloc[-1]), 4) if not pd.isna(dea.iloc[-1]) else 0,
                'macd': round(float(macd.iloc[-1]), 4) if not pd.isna(macd.iloc[-1]) else 0
            }
        except Exception as e:
            logger.error(f"计算MACD失败: {e}")
            return {}
    
    @staticmethod
    def _calculate_kdj(data, n=9):
        """计算KDJ指标"""
        try:
            import pandas as pd
            
            df = pd.DataFrame(data)
            
            # 计算RSV
            low_min = df['low'].rolling(window=n).min()
            high_max = df['high'].rolling(window=n).max()
            rsv = (df['close'] - low_min) / (high_max - low_min) * 100
            
            # 计算K、D、J
            k = rsv.ewm(alpha=1/3).mean()
            d = k.ewm(alpha=1/3).mean()
            j = 3 * k - 2 * d
            
            return {
                'kdj_k': round(float(k.iloc[-1]), 2) if not pd.isna(k.iloc[-1]) else 0,
                'kdj_d': round(float(d.iloc[-1]), 2) if not pd.isna(d.iloc[-1]) else 0,
                'kdj_j': round(float(j.iloc[-1]), 2) if not pd.isna(j.iloc[-1]) else 0
            }
        except Exception as e:
            logger.error(f"计算KDJ失败: {e}")
            return {}
    
    @staticmethod
    def _calculate_rsi(prices, periods=[6, 12, 24]):
        """计算RSI指标"""
        try:
            import pandas as pd
            
            prices = pd.Series(prices)
            delta = prices.diff()
            
            result = {}
            for period in periods:
                if len(prices) >= period:
                    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    
                    result[f'rsi_{period}'] = round(float(rsi.iloc[-1]), 2) if not pd.isna(rsi.iloc[-1]) else 0
            
            return result
        except Exception as e:
            logger.error(f"计算RSI失败: {e}")
            return {}
    
    @staticmethod
    def _calculate_bollinger_bands(prices, window=20, num_std=2):
        """计算布林带指标"""
        try:
            import pandas as pd
            
            prices = pd.Series(prices)
            
            if len(prices) >= window:
                rolling_mean = prices.rolling(window=window).mean()
                rolling_std = prices.rolling(window=window).std()
                
                upper_band = rolling_mean + (rolling_std * num_std)
                lower_band = rolling_mean - (rolling_std * num_std)
                
                return {
                    'boll_upper': round(float(upper_band.iloc[-1]), 2) if not pd.isna(upper_band.iloc[-1]) else 0,
                    'boll_mid': round(float(rolling_mean.iloc[-1]), 2) if not pd.isna(rolling_mean.iloc[-1]) else 0,
                    'boll_lower': round(float(lower_band.iloc[-1]), 2) if not pd.isna(lower_band.iloc[-1]) else 0
                }
            
            return {}
        except Exception as e:
            logger.error(f"计算布林带失败: {e}")
            return {} 
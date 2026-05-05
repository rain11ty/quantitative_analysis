# -*- coding: utf-8 -*-
from app.extensions import db
from sqlalchemy import Column, String, Date, DECIMAL, Index

class StockMoneyflow(db.Model):
    """个股资金流向数据表"""
    __tablename__ = 'stock_moneyflow'

    __table_args__ = (
        Index('idx_stock_moneyflow_trade_date', 'trade_date'),
    )

    ts_code = Column(String(20), primary_key=True, comment='股票代码')
    trade_date = Column(Date, primary_key=True, comment='交易日期')
    
    # 小单
    buy_sm_vol = Column(DECIMAL(20, 2), comment='小单买入量（手）')
    buy_sm_amount = Column(DECIMAL(20, 2), comment='小单买入金额（万元）')
    sell_sm_vol = Column(DECIMAL(20, 2), comment='小单卖出量（手）')
    sell_sm_amount = Column(DECIMAL(20, 2), comment='小单卖出金额（万元）')
    
    # 中单
    buy_md_vol = Column(DECIMAL(20, 2), comment='中单买入量（手）')
    buy_md_amount = Column(DECIMAL(20, 2), comment='中单买入金额（万元）')
    sell_md_vol = Column(DECIMAL(20, 2), comment='中单卖出量（手）')
    sell_md_amount = Column(DECIMAL(20, 2), comment='中单卖出金额（万元）')
    
    # 大单
    buy_lg_vol = Column(DECIMAL(20, 2), comment='大单买入量（手）')
    buy_lg_amount = Column(DECIMAL(20, 2), comment='大单买入金额（万元）')
    sell_lg_vol = Column(DECIMAL(20, 2), comment='大单卖出量（手）')
    sell_lg_amount = Column(DECIMAL(20, 2), comment='大单卖出金额（万元）')
    
    # 特大单
    buy_elg_vol = Column(DECIMAL(20, 2), comment='特大单买入量（手）')
    buy_elg_amount = Column(DECIMAL(20, 2), comment='特大单买入金额（万元）')
    sell_elg_vol = Column(DECIMAL(20, 2), comment='特大单卖出量（手）')
    sell_elg_amount = Column(DECIMAL(20, 2), comment='特大单卖出金额（万元）')
    
    # 净流入
    net_mf_vol = Column(DECIMAL(20, 2), comment='净流入量（手）')
    net_mf_amount = Column(DECIMAL(20, 2), comment='净流入额（万元）')
    
    def to_dict(self):
        """转换为字典"""
        return {
            'ts_code': self.ts_code,
            'trade_date': self.trade_date.isoformat() if self.trade_date is not None else None,
            'buy_sm_vol': float(self.buy_sm_vol) if self.buy_sm_vol is not None else None,
            'buy_sm_amount': float(self.buy_sm_amount) if self.buy_sm_amount is not None else None,
            'sell_sm_vol': float(self.sell_sm_vol) if self.sell_sm_vol is not None else None,
            'sell_sm_amount': float(self.sell_sm_amount) if self.sell_sm_amount is not None else None,
            'buy_md_vol': float(self.buy_md_vol) if self.buy_md_vol is not None else None,
            'buy_md_amount': float(self.buy_md_amount) if self.buy_md_amount is not None else None,
            'sell_md_vol': float(self.sell_md_vol) if self.sell_md_vol is not None else None,
            'sell_md_amount': float(self.sell_md_amount) if self.sell_md_amount is not None else None,
            'buy_lg_vol': float(self.buy_lg_vol) if self.buy_lg_vol is not None else None,
            'buy_lg_amount': float(self.buy_lg_amount) if self.buy_lg_amount is not None else None,
            'sell_lg_vol': float(self.sell_lg_vol) if self.sell_lg_vol is not None else None,
            'sell_lg_amount': float(self.sell_lg_amount) if self.sell_lg_amount is not None else None,
            'buy_elg_vol': float(self.buy_elg_vol) if self.buy_elg_vol is not None else None,
            'buy_elg_amount': float(self.buy_elg_amount) if self.buy_elg_amount is not None else None,
            'sell_elg_vol': float(self.sell_elg_vol) if self.sell_elg_vol is not None else None,
            'sell_elg_amount': float(self.sell_elg_amount) if self.sell_elg_amount is not None else None,
            'net_mf_vol': float(self.net_mf_vol) if self.net_mf_vol is not None else None,
            'net_mf_amount': float(self.net_mf_amount) if self.net_mf_amount is not None else None
        }
    
    def __repr__(self):
        return f'<StockMoneyflow {self.ts_code} {self.trade_date}>' 
import React from 'react';
import { getPHCOverallStatus, getStockStatus, getStockHours } from '../utils/stockUtils';
import { StatusBadge } from './StatusAndStats';
import { MapPin, Clock, AlertTriangle, Bed, Users } from 'lucide-react';

export const PHCCard = ({ phc, onClick }) => {
  const overallStatus = getPHCOverallStatus(phc.stockItems);
  
  // Find the items driving the worst status
  const criticalItems = phc.stockItems.filter(item => getStockStatus(item) === overallStatus);
  // Sort them by hours remaining (lowest first)
  const sortedCriticalItems = criticalItems.sort((a, b) => {
    return getStockHours(a.currentUnits, a.avgDailyConsumption) - getStockHours(b.currentUnits, b.avgDailyConsumption);
  });

  const worstItem = sortedCriticalItems[0];
  const hoursLeft = worstItem ? Math.round(getStockHours(worstItem.currentUnits, worstItem.avgDailyConsumption)) : null;

  const beds = phc.availableBeds ?? 0;
  const doctors = phc.doctorsPresent ?? 0;

  return (
    <div 
      className="bg-white shadow-[0_20px_50px_rgba(0,0,0,0.05)] hover:shadow-[0_25px_60px_rgba(0,0,0,0.08)] p-8 transition-shadow cursor-pointer flex flex-col h-full rounded-sm"
      onClick={() => onClick(phc)}
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-[0.1em] text-[#111] leading-tight mb-2">{phc.name}</h3>
          <div className="flex items-center text-[10px] uppercase tracking-wider text-gray-400 font-medium">
            <MapPin className="h-3 w-3 mr-1" />
            {phc.block}
          </div>
        </div>
        <StatusBadge status={overallStatus} />
      </div>

      {/* Beds & Doctors Row */}
      <div className="flex gap-4 mb-4 py-3 border-y border-slate-100">
        <div className="flex items-center gap-1.5 flex-1">
          <Bed className={`h-4 w-4 ${beds > 5 ? 'text-emerald-500' : beds > 0 ? 'text-amber-500' : 'text-red-500'}`} />
          <div>
            <div className="text-xs font-bold text-slate-800">{beds}</div>
            <div className="text-[9px] uppercase tracking-wider text-slate-400 font-semibold">Beds Free</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-1">
          <Users className={`h-4 w-4 ${doctors >= 2 ? 'text-emerald-500' : doctors === 1 ? 'text-amber-500' : 'text-red-500'}`} />
          <div>
            <div className="text-xs font-bold text-slate-800">{doctors}</div>
            <div className="text-[9px] uppercase tracking-wider text-slate-400 font-semibold">Doctors</div>
          </div>
        </div>
      </div>

      <div className="mt-auto pt-4 border-t border-slate-100">
        {overallStatus !== 'healthy' ? (
          <div className="flex items-start gap-2">
            <AlertTriangle className={`h-4 w-4 mt-0.5 ${overallStatus === 'critical' ? 'text-red-500' : 'text-yellow-500'}`} />
            <div>
              <div className="text-sm font-medium text-slate-800">
                {worstItem.itemName}
              </div>
              <div className="flex items-center text-xs text-slate-500 mt-0.5">
                <Clock className="h-3 w-3 mr-1" />
                Est. {hoursLeft === Infinity ? '∞' : hoursLeft} hours remaining
              </div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-slate-500 flex items-center">
            <Clock className="h-4 w-4 mr-1.5 text-green-500" />
            All stock levels healthy (&gt;72h)
          </div>
        )}
      </div>
    </div>
  );
};


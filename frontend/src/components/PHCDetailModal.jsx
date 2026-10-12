import React from 'react';
import { X, Bed, Users } from 'lucide-react';
import { getStockStatus, getStockHours } from '../utils/stockUtils';
import { StatusBadge } from './StatusAndStats';

export const PHCDetailModal = ({ phc, onClose }) => {
  if (!phc) return null;

  const beds = phc.availableBeds ?? 0;
  const doctors = phc.doctorsPresent ?? 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/20 backdrop-blur-sm">
      <div className="bg-white border border-slate-200 w-full max-w-3xl flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-6 border-b border-slate-100">
          <div>
            <h2 className="text-xl font-light text-slate-900">{phc.name}</h2>
            <div className="text-xs text-slate-500 mt-1 uppercase tracking-wider">{phc.block} Block</div>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-800 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-8 overflow-y-auto">

          {/* Beds & Doctors Summary */}
          <div className="flex gap-6 mb-6 p-4 bg-slate-50 rounded border border-slate-200">
            <div className="flex items-center gap-2">
              <Bed className={`h-5 w-5 ${beds > 5 ? 'text-emerald-500' : beds > 0 ? 'text-amber-500' : 'text-red-500'}`} />
              <div>
                <div className="text-lg font-bold text-slate-800">{beds}</div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Beds Available</div>
              </div>
            </div>
            <div className="w-px bg-slate-200"></div>
            <div className="flex items-center gap-2">
              <Users className={`h-5 w-5 ${doctors >= 2 ? 'text-emerald-500' : doctors === 1 ? 'text-amber-500' : 'text-red-500'}`} />
              <div>
                <div className="text-lg font-bold text-slate-800">{doctors}</div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Doctors Present</div>
              </div>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full text-left border-collapse">
              <thead>
                <tr className="border-b-2 border-slate-100">
                  <th className="py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Item Name</th>
                  <th className="py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Stock</th>
                  <th className="py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Daily Avg</th>
                  <th className="py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Hours Left</th>
                  <th className="py-3 pl-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {phc.stockItems.map((item, idx) => {
                  const status = getStockStatus(item);
                  const hours = Math.round(getStockHours(item.currentUnits, item.avgDailyConsumption));
                  
                  return (
                    <tr key={idx} className="hover:bg-slate-50/50 transition-colors">
                      <td className="py-4 text-sm text-slate-900">{item.itemName}</td>
                      <td className="py-4 text-sm text-slate-600 text-right font-light">{item.currentUnits.toLocaleString()}</td>
                      <td className="py-4 text-sm text-slate-600 text-right font-light">{item.avgDailyConsumption}</td>
                      <td className="py-4 text-sm text-slate-600 text-right font-light">
                        {hours === Infinity ? '∞' : hours}
                      </td>
                      <td className="py-4 pl-6">
                        <StatusBadge status={status} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          
          <div className="mt-4 text-xs text-slate-500 flex justify-end">
            Last updated: {new Date(phc.lastUpdated).toLocaleString()}
          </div>
        </div>

      </div>
    </div>
  );
};

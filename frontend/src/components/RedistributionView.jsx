import React, { useMemo, useState } from 'react';
import { suggestTransfers } from '../utils/suggestTransfers';
import { ArrowRight, Box } from 'lucide-react';

export const RedistributionView = ({ phcs }) => {
  const [selectedItem, setSelectedItem] = useState('All');
  
  const transfers = useMemo(() => suggestTransfers(phcs), [phcs]);

  const itemsWithTransfers = useMemo(() => {
    const items = new Set(transfers.map(t => t.itemName));
    return Array.from(items).sort();
  }, [transfers]);

  const filteredTransfers = useMemo(() => {
    let filtered = transfers;
    if (selectedItem !== 'All') {
      filtered = transfers.filter(t => t.itemName === selectedItem);
    }
    // Sort by hours impact (highest first) to prioritize the most critical transfers
    return filtered.sort((a, b) => b.hoursImpact - a.hoursImpact);
  }, [transfers, selectedItem]);

  return (
    <div className="flex flex-col h-full min-h-[calc(100vh-8rem)]">
      <div className="flex justify-between items-end mb-8 border-b-2 border-[#111] pb-4">
        <div>
          <h2 className="text-xl font-bold tracking-[0.1em] text-[#111] uppercase">Actionable Transfers</h2>
          <p className="text-xs text-gray-500 mt-1 uppercase tracking-wider font-medium">Recommended routing to prevent stock-outs</p>
        </div>
        
        <select
          className="block w-64 py-2 pl-0 pr-6 text-xs font-bold uppercase tracking-wider border-0 border-b-2 border-gray-200 bg-transparent focus:outline-none focus:border-[#111] transition-colors"
          value={selectedItem}
          onChange={(e) => setSelectedItem(e.target.value)}
        >
          <option value="All">All Items</option>
          {itemsWithTransfers.map(item => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
      </div>

      {filteredTransfers.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-gray-400 font-light uppercase tracking-widest text-sm">No critical shortages require redistribution.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 pb-12">
          {filteredTransfers.map((t, idx) => (
            <div key={idx} className="bg-white p-6 shadow-[0_15px_40px_rgba(0,0,0,0.04)] hover:shadow-[0_20px_50px_rgba(0,0,0,0.08)] transition-shadow border border-gray-100 flex flex-col">
              
              <div className="flex items-center gap-3 mb-6">
                <div className="h-10 w-10 bg-[#111] text-white flex items-center justify-center shrink-0">
                  <Box className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-sm font-bold uppercase tracking-[0.1em] text-[#111] leading-tight">
                    {t.itemName}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-green-600 font-bold mt-1">
                    +{t.hoursImpact} hours secured
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-4 mt-auto">
                <div className="bg-gray-50 p-4 flex flex-col border border-gray-100 relative">
                  <span className="absolute -top-2 left-4 bg-gray-200 text-gray-600 text-[8px] uppercase tracking-wider px-2 py-0.5 font-bold">Source</span>
                  <div className="text-xs font-bold uppercase tracking-wider text-[#111]">{t.sourceName}</div>
                  <div className="text-[10px] uppercase tracking-widest text-gray-400 mt-1">Surplus Available</div>
                </div>

                <div className="flex justify-center -my-3 z-10">
                  <div className="bg-[#111] text-white px-4 py-1.5 flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest rounded-full shadow-lg">
                    Transfer {t.quantity} <ArrowRight className="h-3 w-3" />
                  </div>
                </div>

                <div className="bg-red-50 p-4 flex flex-col border border-red-100 relative">
                  <span className="absolute -top-2 left-4 bg-red-200 text-red-700 text-[8px] uppercase tracking-wider px-2 py-0.5 font-bold">Destination</span>
                  <div className="text-xs font-bold uppercase tracking-wider text-[#111]">{t.targetName}</div>
                  <div className="text-[10px] uppercase tracking-widest text-red-500 mt-1">Critical Shortage</div>
                </div>
              </div>

            </div>
          ))}
        </div>
      )}
    </div>
  );
};

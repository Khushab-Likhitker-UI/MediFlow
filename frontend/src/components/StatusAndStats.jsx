import React from 'react';
import { getPHCOverallStatus } from '../utils/stockUtils';

export const StatusBadge = ({ status }) => {
  const colors = {
    healthy: "text-green-500 bg-green-500/10",
    warning: "text-yellow-500 bg-yellow-500/10",
    critical: "text-red-500 bg-red-500/10"
  };

  return (
    <span className={`px-2 py-1 rounded-sm text-[9px] font-bold uppercase tracking-[0.15em] ${colors[status]}`}>
      {status}
    </span>
  );
};

export const SummaryStats = ({ phcs }) => {
  const counts = { total: phcs.length, healthy: 0, warning: 0, critical: 0 };
  
  phcs.forEach(phc => {
    const status = getPHCOverallStatus(phc.stockItems);
    counts[status]++;
  });

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-12">
      <div className="bg-[#111] text-white rounded-sm p-6 shadow-2xl flex flex-col justify-center">
        <div className="text-[10px] font-medium text-gray-400 uppercase tracking-[0.2em]">Total PHCs</div>
        <div className="mt-2 text-4xl font-light tracking-tighter">{counts.total}</div>
      </div>
      <div className="bg-[#111] text-white rounded-sm p-6 shadow-2xl flex flex-col justify-center border-l-2 border-green-500">
        <div className="text-[10px] font-medium text-green-500 uppercase tracking-[0.2em]">Healthy</div>
        <div className="mt-2 text-4xl font-light tracking-tighter">{counts.healthy}</div>
      </div>
      <div className="bg-[#111] text-white rounded-sm p-6 shadow-2xl flex flex-col justify-center border-l-2 border-yellow-500">
        <div className="text-[10px] font-medium text-yellow-500 uppercase tracking-[0.2em]">Warning</div>
        <div className="mt-2 text-4xl font-light tracking-tighter">{counts.warning}</div>
      </div>
      <div className="bg-[#111] text-white rounded-sm p-6 shadow-2xl flex flex-col justify-center border-l-2 border-red-500">
        <div className="text-[10px] font-medium text-red-500 uppercase tracking-[0.2em]">Critical</div>
        <div className="mt-2 text-4xl font-light tracking-tighter">{counts.critical}</div>
      </div>
    </div>
  );
};

import React, { useMemo, useState } from 'react';
import { Sankey, Tooltip, ResponsiveContainer } from 'recharts';
import { suggestTransfers } from '../utils/suggestTransfers';

export const RedistributionSankey = ({ phcs }) => {
  const [selectedItem, setSelectedItem] = useState('All');
  
  const transfers = useMemo(() => suggestTransfers(phcs), [phcs]);

  const itemsWithTransfers = useMemo(() => {
    const items = new Set(transfers.map(t => t.itemName));
    return Array.from(items).sort();
  }, [transfers]);

  const chartData = useMemo(() => {
    let filteredTransfers = transfers;
    if (selectedItem !== 'All') {
      filteredTransfers = transfers.filter(t => t.itemName === selectedItem);
    }
    
    // Limit to max 10 links to avoid clutter
    filteredTransfers = filteredTransfers.slice(0, 10);

    const nodesMap = new Map();
    const links = [];

    // Assign node indices
    let nodeIndex = 0;
    const getNodeIndex = (name) => {
      if (!nodesMap.has(name)) {
        nodesMap.set(name, nodeIndex++);
      }
      return nodesMap.get(name);
    };

    filteredTransfers.forEach(t => {
      const sourceIdx = getNodeIndex(`${t.sourceName} (Surplus)`);
      const targetIdx = getNodeIndex(`${t.targetName} (Shortage)`);
      
      links.push({
        source: sourceIdx,
        target: targetIdx,
        value: t.quantity,
        payload: t // for tooltip
      });
    });

    const nodes = Array.from(nodesMap.keys()).map(name => ({ name }));

    return { nodes, links };
  }, [transfers, selectedItem]);

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      if (data.payload) { // This is a link tooltip
        const t = data.payload;
        return (
          <div className="bg-white p-4 border-2 border-[#111] shadow-[0_15px_40px_rgba(0,0,0,0.1)]">
            <p className="font-bold uppercase tracking-[0.1em] text-[#111] mb-2">{t.itemName}</p>
            <p className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Source: <span className="font-bold text-[#111]">{t.sourceName}</span></p>
            <p className="text-[10px] uppercase tracking-wider text-gray-500 mb-2">Target: <span className="font-bold text-[#111]">{t.targetName}</span></p>
            <div className="bg-gray-50 border border-gray-200 p-2 text-center mt-2">
              <p className="text-xs uppercase tracking-widest text-[#111] font-bold">Transfer {t.quantity} units</p>
            </div>
            <p className="text-[10px] text-green-600 font-bold uppercase tracking-wider mt-2 text-center">+{t.hoursImpact} hrs secured</p>
          </div>
        );
      }
      // This is a node tooltip
      return (
        <div className="bg-[#111] text-white p-3 shadow-xl">
          <p className="font-bold text-xs uppercase tracking-wider">{data.name}</p>
          <p className="text-[10px] text-gray-400 mt-1 uppercase tracking-widest">Volume: {data.value}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="flex justify-between items-end mb-8 border-b-2 border-[#111] pb-4">
        <div>
          <h2 className="text-xl font-bold tracking-[0.1em] text-[#111] uppercase">Redistribution Flow</h2>
          <p className="text-xs text-gray-500 mt-1 uppercase tracking-wider font-medium">Matching critical shortages with local surpluses</p>
        </div>
        
        <select
          className="block w-64 py-2 pl-0 pr-6 text-xs font-bold uppercase tracking-wider border-0 border-b-2 border-gray-200 bg-transparent focus:outline-none focus:border-[#111] transition-colors"
          value={selectedItem}
          onChange={(e) => setSelectedItem(e.target.value)}
        >
          <option value="All">All Items (Top 10 Flows)</option>
          {itemsWithTransfers.map(item => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
      </div>

      {chartData.nodes.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-gray-400 font-light uppercase tracking-widest text-sm">No redistribution flows available for selected criteria.</div>
        </div>
      ) : (
        <div className="flex-1 min-h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <Sankey
              data={chartData}
              node={{ stroke: '#111', strokeWidth: 2, fill: '#fff' }}
              nodePadding={40}
              margin={{ left: 20, right: 20, top: 20, bottom: 20 }}
              link={{ stroke: '#e5e7eb' }} // light gray links
            >
              <Tooltip content={<CustomTooltip />} />
            </Sankey>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

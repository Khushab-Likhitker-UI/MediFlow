import React, { useState, useMemo } from 'react';
import { PHCCard } from './PHCCard';
import { FilterBar } from './FilterBar';
import { SummaryStats } from './StatusAndStats';
import { PHCDetailModal } from './PHCDetailModal';
import { AddPHCModal } from './AddPHCModal';
import { getPHCOverallStatus } from '../utils/stockUtils';
import { Plus } from 'lucide-react';

export const PHCGrid = ({ phcs, onAddPHC }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterBlock, setFilterBlock] = useState('All');
  const [filterStatus, setFilterStatus] = useState('All');
  const [sortBy, setSortBy] = useState('severity');
  const [selectedPHC, setSelectedPHC] = useState(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const blocks = useMemo(() => {
    const blockSet = new Set(phcs.map(p => p.block));
    return Array.from(blockSet).sort();
  }, [phcs]);

  const filteredAndSortedPHCs = useMemo(() => {
    // Filter
    let result = phcs.filter(phc => {
      const matchesSearch = phc.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesBlock = filterBlock === 'All' || phc.block === filterBlock;
      const overallStatus = getPHCOverallStatus(phc.stockItems);
      const matchesStatus = filterStatus === 'All' || overallStatus === filterStatus;
      
      return matchesSearch && matchesBlock && matchesStatus;
    });

    // Sort
    result.sort((a, b) => {
      if (sortBy === 'name') {
        return a.name.localeCompare(b.name);
      }
      if (sortBy === 'block') {
        return a.block.localeCompare(b.block);
      }
      if (sortBy === 'severity') {
        const statusMap = { 'critical': 3, 'warning': 2, 'healthy': 1 };
        const statusA = statusMap[getPHCOverallStatus(a.stockItems)];
        const statusB = statusMap[getPHCOverallStatus(b.stockItems)];
        if (statusA !== statusB) {
          return statusB - statusA; // Critical first
        }
        return a.name.localeCompare(b.name); // Tie breaker
      }
      return 0;
    });

    return result;
  }, [phcs, searchTerm, filterBlock, filterStatus, sortBy]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-end mb-4">
        <h2 className="text-xl font-bold tracking-[0.1em] text-[#111] uppercase">Overview</h2>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="flex items-center gap-2 bg-[#111] text-white px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] hover:bg-black transition-colors"
        >
          <Plus className="h-4 w-4" /> Add PHC
        </button>
      </div>

      <SummaryStats phcs={phcs} />
      
      <FilterBar 
        searchTerm={searchTerm} setSearchTerm={setSearchTerm}
        filterBlock={filterBlock} setFilterBlock={setFilterBlock}
        filterStatus={filterStatus} setFilterStatus={setFilterStatus}
        sortBy={sortBy} setSortBy={setSortBy}
        blocks={blocks}
      />

      {filteredAndSortedPHCs.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center py-20 bg-transparent">
          <div className="text-gray-400 mb-2 font-light uppercase tracking-widest text-sm">No PHCs match your filters</div>
          <button 
            onClick={() => {
              setSearchTerm('');
              setFilterBlock('All');
              setFilterStatus('All');
            }}
            className="text-gray-500 hover:text-[#111] text-xs font-bold tracking-[0.1em] uppercase border-b-2 border-gray-300 hover:border-[#111] transition-all pb-1 mt-4"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
          {filteredAndSortedPHCs.map(phc => (
            <PHCCard key={phc.id} phc={phc} onClick={setSelectedPHC} />
          ))}
        </div>
      )}

      <PHCDetailModal phc={selectedPHC} onClose={() => setSelectedPHC(null)} />
      {isAddModalOpen && (
        <AddPHCModal 
          onClose={() => setIsAddModalOpen(false)} 
          onAdd={(newPHC) => {
            onAddPHC(newPHC);
            setIsAddModalOpen(false);
          }} 
        />
      )}
    </div>
  );
};

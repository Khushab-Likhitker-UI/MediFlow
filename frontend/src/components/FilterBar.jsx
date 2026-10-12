import React from 'react';
import { Search, Filter, ArrowUpDown } from 'lucide-react';

export const FilterBar = ({ 
  searchTerm, setSearchTerm, 
  filterBlock, setFilterBlock, 
  filterStatus, setFilterStatus,
  sortBy, setSortBy,
  blocks
}) => {
  return (
    <div className="mb-8 flex flex-col md:flex-row gap-6 items-center justify-between pb-6">
      
      <div className="relative w-full md:w-1/3">
        <div className="absolute inset-y-0 left-0 flex items-center pointer-events-none">
          <Search className="h-4 w-4 text-[#111]" />
        </div>
        <input
          type="text"
          className="block w-full pl-8 pr-3 py-2 text-sm font-medium border-0 border-b-2 border-gray-200 bg-transparent placeholder-gray-400 focus:outline-none focus:border-[#111] transition-colors uppercase tracking-wider"
          placeholder="SEARCH PHC..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      <div className="flex flex-col sm:flex-row w-full md:w-auto gap-8">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-[#111]" />
          <select
            className="block w-full py-2 pl-0 pr-6 text-xs font-medium uppercase tracking-wider border-0 border-b-2 border-gray-200 bg-transparent focus:outline-none focus:border-[#111] transition-colors"
            value={filterBlock}
            onChange={(e) => setFilterBlock(e.target.value)}
          >
            <option value="All">All Blocks</option>
            {blocks.map(block => (
              <option key={block} value={block}>{block}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <select
            className="block w-full py-2 pl-0 pr-6 text-xs font-medium uppercase tracking-wider border-0 border-b-2 border-gray-200 bg-transparent focus:outline-none focus:border-[#111] transition-colors"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="All">All Statuses</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="healthy">Healthy</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <ArrowUpDown className="h-4 w-4 text-[#111]" />
          <select
            className="block w-full py-2 pl-0 pr-6 text-xs font-medium uppercase tracking-wider border-0 border-b-2 border-gray-200 bg-transparent focus:outline-none focus:border-[#111] transition-colors"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="severity">Sort By Severity</option>
            <option value="name">Sort By Name</option>
            <option value="block">Sort By Block</option>
          </select>
        </div>
      </div>

    </div>
  );
};

import { getStockStatus, getStockHours } from './stockUtils';

export const suggestTransfers = (phcs) => {
  const transfers = [];
  const shortages = [];
  const surpluses = [];

  // Identify shortages (critical) and surpluses (>150% of 72h healthy stock = >108h)
  phcs.forEach(phc => {
    phc.stockItems.forEach(item => {
      const status = getStockStatus(item);
      const hours = getStockHours(item.currentUnits, item.avgDailyConsumption);
      
      if (status === "critical") {
        // Need to reach at least 72 hours (healthy)
        const targetUnits = (72 / 24) * item.avgDailyConsumption;
        const deficit = Math.ceil(targetUnits - item.currentUnits);
        if (deficit > 0) {
          shortages.push({
            phcId: phc.id,
            phcName: phc.name,
            block: phc.block,
            itemName: item.itemName,
            deficit: deficit,
            avgDailyConsumption: item.avgDailyConsumption
          });
        }
      } else if (hours > 108) { // 150% of 72 hours
        const healthyUnits = (72 / 24) * item.avgDailyConsumption;
        const availableSurplus = Math.floor(item.currentUnits - healthyUnits);
        if (availableSurplus > 0) {
          surpluses.push({
            phcId: phc.id,
            phcName: phc.name,
            block: phc.block,
            itemName: item.itemName,
            available: availableSurplus
          });
        }
      }
    });
  });

  // Attempt to fulfill shortages
  shortages.forEach(shortage => {
    // Find all surpluses for this item
    let relevantSurpluses = surpluses.filter(s => s.itemName === shortage.itemName && s.available > 0);
    
    // Sort surpluses to prioritize same block first
    relevantSurpluses.sort((a, b) => {
      if (a.block === shortage.block && b.block !== shortage.block) return -1;
      if (a.block !== shortage.block && b.block === shortage.block) return 1;
      return b.available - a.available; // Then by largest available
    });

    for (const surplus of relevantSurpluses) {
      if (shortage.deficit <= 0) break;
      
      const transferQuantity = Math.min(shortage.deficit, surplus.available);
      if (transferQuantity > 0) {
        // Impact calculation
        const hoursGained = shortage.avgDailyConsumption > 0 
          ? (transferQuantity / shortage.avgDailyConsumption) * 24 
          : 0;

        transfers.push({
          sourceId: surplus.phcId,
          targetId: shortage.phcId,
          sourceName: surplus.phcName,
          targetName: shortage.phcName,
          itemName: shortage.itemName,
          quantity: transferQuantity,
          hoursImpact: Math.round(hoursGained)
        });

        // Update remaining balances
        shortage.deficit -= transferQuantity;
        surplus.available -= transferQuantity;
      }
    }
  });

  return transfers;
};

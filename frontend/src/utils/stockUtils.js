export const getStockHours = (currentUnits, avgDailyConsumption) => {
  if (avgDailyConsumption === 0) return Infinity;
  return (currentUnits / avgDailyConsumption) * 24;
};

export const getStockStatus = (stockItem) => {
  const hours = getStockHours(stockItem.currentUnits, stockItem.avgDailyConsumption);
  if (hours > 72) return "healthy";
  if (hours >= 48 && hours <= 72) return "warning";
  return "critical";
};

export const getPHCOverallStatus = (stockItems) => {
  if (!stockItems || stockItems.length === 0) return "healthy";
  
  let worstStatus = "healthy";
  for (const item of stockItems) {
    const status = getStockStatus(item);
    if (status === "critical") return "critical"; // Can't get worse than critical
    if (status === "warning") worstStatus = "warning";
  }
  return worstStatus;
};

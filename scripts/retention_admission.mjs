// Retention admission only: never deletes data or changes storage limits.
export function checkRetentionHeadroom(retainedBytes, policy, requestedGrowthBytes = policy.maximumRunGrowthBytes) {
  for (const value of [retainedBytes, policy.maximumRetainedBytes, policy.maximumRunGrowthBytes, requestedGrowthBytes])
    if (!Number.isSafeInteger(value) || value < 0) throw new Error('Unknown retention accounting; admission refused');
  if (requestedGrowthBytes > policy.maximumRunGrowthBytes)
    throw new Error('Requested growth exceeds the approved per-run limit');
  if (retainedBytes > policy.maximumRetainedBytes ||
      requestedGrowthBytes > policy.maximumRetainedBytes - retainedBytes)
    throw new Error('Insufficient retained-output headroom: retain compact evidence, review an exact deletion inventory, and obtain approval before removing files');
  return {retainedBytes, reservedGrowthBytes: requestedGrowthBytes,
    remainingAfterReservationBytes: policy.maximumRetainedBytes - retainedBytes - requestedGrowthBytes,
    filesDeleted: 0};
}
export function retentionInventory(inventory, policy, onAdmission = () => {}) {
  return roots => {
    const retained = inventory(roots);
    onAdmission(checkRetentionHeadroom(retained, policy));
    return retained;
  };
}

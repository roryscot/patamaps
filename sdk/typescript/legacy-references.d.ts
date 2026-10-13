export declare function isLegacyReferenceIdentifier(
  value: unknown,
): value is string;
export declare function isLegacyRelationIdentifier(
  value: unknown,
): value is string;
export declare function makeLegacyUrn(
  namespace: string,
  kind: string,
  value: string,
): string;
export declare function makeLegacyRepositoryUri(
  rawPath: string,
  repository?: string,
): string;
export declare function hasLegacyAmbiguousPathLanguage(path: string): boolean;
export declare function isLegacyPathPattern(path: string): boolean;

import { useStore } from '@/store/useStore';
import { OpenquireAdapter } from '@/lib/openquireAdapter';

export interface PlatformDomainInfo {
  id: string;
  name: string;
  description?: string;
  sectionTemplates?: Record<string, any>;
  fieldAliases?: Record<string, string[]>;
  intents?: string[];
}

export abstract class PlatformAdapter {
  protected readonly domain: string;

  constructor(domain: string) {
    this.domain = domain;
  }

  getCurrentDomain(): string {
    return this.domain;
  }

  protected getDomainInfo(): PlatformDomainInfo {
    const state = useStore.getState();
    const match = state.domains.find(
      (d) => d.name === this.domain || d.id === this.domain,
    );
    return {
      id: match?.id ?? this.domain,
      name: match?.name ?? this.domain,
      description: match?.description,
    };
  }

  abstract getSectionTemplates(): Promise<Record<string, any>>;
  abstract getFieldAliases(): Promise<Record<string, string[]>>;
  abstract getDomainIntents(): Promise<string[]>;
  abstract aggregateFormSchema(
    rawSchema: Record<string, any>,
  ): Promise<Record<string, any>>;
  abstract getMappingConfig(fieldId: string): Promise<{
    sourceKey?: string;
    value?: string;
    confidence?: number;
  }>;
}

export function createPlatformAdapter(): PlatformAdapter {
  const domain = useStore.getState().domain;
  return new OpenquireAdapter(domain);
}

/**
 * Return the platform adapter for the currently-selected domain.
 *
 * Domain-agnostic: every active domain registered in the backend is valid;
 * the adapter is built from the domain slug held in the store rather than a
 * hardcoded list of "supported" domain names.
 */
export function getPlatformAdapter(): PlatformAdapter | null {
  const domain = useStore.getState().domain;
  if (!domain) return null;
  return new OpenquireAdapter(domain);
}
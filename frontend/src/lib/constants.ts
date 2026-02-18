import { Monitor, Server, HardDrive, Shield } from 'lucide-react';
import type { KBCategory } from '../types';

export const CATEGORIES: { key: KBCategory; label: string; icon: typeof Monitor; colour: string }[] = [
  { key: 'Frontend', label: 'Frontend', icon: Monitor, colour: 'blue' },
  { key: 'Backend', label: 'Backend', icon: Server, colour: 'purple' },
  { key: 'Infrastructure', label: 'Infrastructure', icon: HardDrive, colour: 'orange' },
  { key: 'Security', label: 'Security', icon: Shield, colour: 'red' },
];

export const KB_CATEGORIES: KBCategory[] = CATEGORIES.map(c => c.key);

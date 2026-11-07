export type PreviewRole = 'PADRE' | 'GUARDIA';
export function previewFor(role: PreviewRole): { message: string; canAuthorize: false } {
  return {
    message: role === 'PADRE'
      ? 'Padre: la consulta de estudiantes y autorizaciones aún no está disponible.'
      : 'Guardia: el escaneo y la confirmación aún no están disponibles.',
    canAuthorize: false,
  };
}

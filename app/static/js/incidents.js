/* incidents.js — confirmation actions SOAR */
(function () {
  /* Les modals Bootstrap gèrent déjà la confirmation — ce fichier
     est un point d'extension pour les filtres dynamiques futurs. */

  /* Auto-submit du formulaire de filtre quand un select change */
  const filterForm = document.querySelector('form[action*="incidents"]');
  if (filterForm) {
    filterForm.querySelectorAll('select').forEach(sel => {
      sel.addEventListener('change', () => filterForm.submit());
    });
  }
})();

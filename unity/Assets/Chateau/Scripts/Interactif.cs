// Objet activable avec E (ou le bouton Porte en tactile) quand l'explorateur le vise : trappe du toit, scooter.
// Les portes et les repères d'histoire gardent leurs propres composants.
public interface IInteractif
{
    string Libelle(Explorateur explorateur);
    void Interagir(Explorateur explorateur);
}

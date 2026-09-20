import { Sprout } from 'lucide-react';

const steps = [
  {
    title: 'Browse and compare',
    body: 'Every listing shows how long the produce has been off the plant, so you can compare freshness before price.',
  },
  {
    title: 'Request an order',
    body: 'A signed-in buyer picks a quantity. You see the full amount before anything is confirmed.',
  },
  {
    title: 'The farmer confirms',
    body: 'Your request goes straight to the grower. They accept it and set it aside from that day\u2019s harvest.',
  },
  {
    title: 'Collect or deliver',
    body: 'Pick up from the farm, or arrange delivery on a route that already passes nearby.',
  },
];

export default function HowItWorks() {
  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">How it works</span>
        <h1>From harvest to your kitchen</h1>
        <p>
          FarmLink removes the layers between the person growing the food and the person eating it. Here is what
          happens between a listing going up and produce arriving at your door.
        </p>
      </div>
      <section className="section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Four steps</span>
            <h2>What happens after you order</h2>
          </div>
        </div>
        <div className="product-grid">
          {steps.map((s, i) => (
            <article className="product-card" key={s.title}>
              <div className="product-body">
                <div className="card-top">
                  <span className="badge fresh">Step {i + 1}</span>
                </div>
                <h3>{s.title}</h3>
                <p className="muted">{s.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="impact">
        <div>
          <Sprout size={30} />
          <h2>One marketplace. Better outcomes.</h2>
        </div>
        <p>FarmLink helps growers sell directly, helps buyers see where food comes from, and keeps delivery planning simple.</p>
        <div className="impact-items">
          <span>
            <b>Direct prices</b>No unnecessary middle layers
          </span>
          <span>
            <b>Freshness first</b>Clear shelf-life indicators
          </span>
          <span>
            <b>Smarter delivery</b>Practical route planning
          </span>
        </div>
      </section>
    </main>
  );
}

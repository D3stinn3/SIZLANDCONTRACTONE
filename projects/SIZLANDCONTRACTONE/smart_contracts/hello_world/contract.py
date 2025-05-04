from algopy import Account, ARC4Contract, Asset, BoxMap, Global, Txn, arc4, itxn
from algopy.arc4 import Struct


class UserAllocation(Struct):
    total_allocation: arc4.UInt64
    claimed_amount: arc4.UInt64
    start_time: arc4.UInt64
    cliff_time: arc4.UInt64
    vesting_period: arc4.UInt64
    last_claim_time: arc4.UInt64


class SizlandVestingContract(ARC4Contract):
    # Define state variables for vesting  parameters
    # For example: beneficiary, total amount, vesting period, etc.

    def __init__(self) -> None:
        # Initialize your contract state
        # This will be executed once on deployment
        self.asa = Asset()
        self.allocations = BoxMap(Account, UserAllocation, key_prefix="")

    @arc4.abimethod
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into a ASA
        assert Txn.sender == Global.creator_address, "Only creator can opt in to ASA"
        # Verify a ASA hasn't already been opted into
        assert self.asa.id == 2905622564, "ASA already opted in"
        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        itxn.AssetTransfer(
            asset_receiver=Global.current_application_address,
            xfer_asset=asset,
        ).submit()

    @arc4.abimethod
    def set_allocation(
        self,
        beneficiary: Account,
        total_allocation: arc4.UInt64,
        start_time: arc4.UInt64,
        cliff_time: arc4.UInt64,
        vesting_period: arc4.UInt64,
    ) -> None:
        assert (
            Txn.sender == Global.creator_address
        ), "Only the creator can call this method"
        self.allocations[beneficiary] = UserAllocation(
            total_allocation=total_allocation,
            claimed_amount=arc4.UInt64(0),
            start_time=start_time,
            cliff_time=cliff_time,
            vesting_period=vesting_period,
            last_claim_time=arc4.UInt64(0),
        )

    @arc4.abimethod
    def claim(self) -> None:
        current_time = arc4.UInt64(Global.latest_timestamp)
        sender = Txn.sender

        allocation, exists = self.allocations.maybe(sender)
        assert exists, "No allocation found"

        # Check if cliff has passed
        assert current_time >= allocation.cliff_time, "Cliff not reached"

        # Optional: Enforce cooldown period (e.g. 10 seconds between claims)
        assert current_time - allocation.last_claim_time >= arc4.UInt64(
            10
        ), "Wait before claiming again"

        # Calculate how much is vested
        end_time = allocation.start_time + allocation.vesting_period

        if current_time >= end_time:
            # Fully vested
            vested_amount = allocation.total_allocation
        else:
            # Linear vesting
            elapsed = current_time - allocation.start_time
            vested_amount = (
                allocation.total_allocation * elapsed
            ) // allocation.vesting_period

        # Calculate how much is claimable
        claimable = vested_amount - allocation.claimed_amount
        assert claimable > 0, "Nothing to claim"

        # Transfer ASA to user
        itxn.AssetTransfer(
            asset_receiver=sender,
            asset_amount=claimable,
            xfer_asset=self.asa,
        ).submit()

        # Update allocation
        self.allocations[sender] = UserAllocation(
            total_allocation=allocation.total_allocation,
            claimed_amount=allocation.claimed_amount + claimable,
            start_time=allocation.start_time,
            cliff_time=allocation.cliff_time,
            vesting_period=allocation.vesting_period,
            last_claim_time=current_time,
        )
